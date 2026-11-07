"""Image validation, quality scoring and local OCR (Tesseract) – DFD 2.0 for image input.

OCR runs locally on the server, so the image never leaves it unless the user has consented to
AI processing (Gemini extraction).
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings

log = logging.getLogger(__name__)
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIDE = 2200


class ImageError(ValueError):
    pass


@dataclass
class OcrLine:
    text: str
    conf: float  # 0..1 mean word confidence


@dataclass
class OcrResult:
    available: bool
    engine: str = "none"
    text: str = ""
    lines: list[OcrLine] = field(default_factory=list)
    mean_conf: float = 0.0


def load_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageError("This file is not a readable image. Please upload a JPG, PNG or WEBP photo.") from exc
    if fmt not in ALLOWED_FORMATS:
        raise ImageError("Unsupported image type. Please upload a JPG, PNG or WEBP photo.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def to_jpeg_bytes(img: Image.Image, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def assess_quality(img: Image.Image) -> dict:
    """Cheap, explainable image-quality checks (resolution, sharpness, brightness, contrast)."""
    w, h = img.size
    g = np.asarray(ImageOps.grayscale(img), dtype=np.float32)
    # variance of Laplacian on a normalised ~1000px-wide version (sharpness proxy)
    scale = 1000 / max(w, 1)
    if scale < 1:
        g_small = np.asarray(ImageOps.grayscale(img).resize((1000, max(int(h * scale), 1))), dtype=np.float32)
    else:
        g_small = g
    lap = (-4 * g_small[1:-1, 1:-1] + g_small[:-2, 1:-1] + g_small[2:, 1:-1] + g_small[1:-1, :-2] + g_small[1:-1, 2:])
    sharp = float(lap.var())
    bright, contrast = float(g.mean()), float(g.std())
    warnings = []
    if max(w, h) < 900:
        warnings.append("low_resolution")
    if sharp < 40:
        warnings.append("blurry")
    if bright < 70:
        warnings.append("too_dark")
    if bright > 248:  # plain white paper scans average ~240; only flag genuinely blown-out photos
        warnings.append("overexposed")
    if contrast < 25:
        warnings.append("low_contrast")
    return {
        "width": w, "height": h, "sharpness": round(sharp, 1), "brightness": round(bright, 1),
        "contrast": round(contrast, 1), "warnings": warnings, "ok": not warnings,
    }


def run_ocr(img: Image.Image) -> OcrResult:
    try:
        import pytesseract
        from pytesseract import Output

        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001 – module missing or binary missing
        return OcrResult(available=False)
    prepared = ImageOps.autocontrast(ImageOps.grayscale(img))
    if max(prepared.size) < 1400:  # upscale small photos – helps Tesseract on small print
        f = 1400 / max(prepared.size)
        prepared = prepared.resize((int(prepared.width * f), int(prepared.height * f)), Image.LANCZOS)
    try:
        d = pytesseract.image_to_data(prepared, lang=get_settings().ocr_languages, config="--psm 6", output_type=Output.DICT, timeout=45)
    except Exception as exc:  # noqa: BLE001
        log.warning("Tesseract failed: %s", type(exc).__name__)
        return OcrResult(available=False)
    lines: dict[tuple, list[tuple[str, float]]] = {}
    for i, word in enumerate(d["text"]):
        word = word.strip()
        try:
            conf = float(d["conf"][i])
        except (TypeError, ValueError):
            continue
        if not word or conf < 0:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        lines.setdefault(key, []).append((word, conf / 100.0))
    out = [OcrLine(" ".join(w for w, _ in ws), sum(c for _, c in ws) / len(ws)) for ws in lines.values()]
    allw = [c for ws in lines.values() for _, c in ws]
    return OcrResult(True, "tesseract", "\n".join(l.text for l in out), out, sum(allw) / len(allw) if allw else 0.0)
