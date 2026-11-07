import io
import json

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def prescription_image(lines: list[str], size=(1400, 1000), font_size=40, blur=0.0) -> bytes:
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, font_size)
    y = 60
    for ln in lines:
        d.text((60, y), ln, fill="black", font=f)
        y += font_size + 30
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


SAMPLE_LINES = [
    "Dr. Ramesh Kumar  MBBS",
    "Date: 12/10/2026",
    "Rx",
    "1) Tab Metformin 500mg 1-0-1 after food x 30 days",
    "2) Tab Amlodipine 5mg 0-0-1 at night x 30 days",
    "3) Cap Omeprazole 20mg 1-0-0 before food x 14 days",
]


def gemini_transport(handler):
    """httpx MockTransport that stands in for Google's API."""
    return httpx.MockTransport(handler)


def gemini_text_response(payload: dict | str) -> httpx.Response:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]})


def install_fake_gemini(handler):
    from app.services import gemini

    c = gemini.GeminiClient("test-key", "gemini-test", "embed-test", transport=gemini_transport(handler))
    gemini.set_gemini(c)
    return c
