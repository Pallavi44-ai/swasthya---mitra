"""RAG over curated healthcare notes (DFD store D4, report §4.9).

Retrieval = BM25 (always available, offline) fused with Gemini embeddings (when configured and
the user has consented to AI processing) using reciprocal-rank fusion. Embeddings are what make
Hindi/Kannada/Telugu queries retrievable against the English notes; BM25 alone only matches English.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import KnowledgeChunk
from app.services.gemini import GeminiError, get_gemini

log = logging.getLogger(__name__)
KB_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"
MAX_WORDS = 170

_STOP = set(
    "a an the and or of to in on for with is are was were be been it this that these those at by from as "
    "i my me you your we our he she they them his her do does did can could should would will may might "
    "have has had not no yes what when where which who why how about into than then so if but also".split()
)


@dataclass
class Passage:
    id: str
    title: str
    section: str
    text: str
    source_name: str
    source_url: str | None
    review_status: str
    score: float


# ---- ingestion ----------------------------------------------------------------------------------
def _parse_doc(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
    if not m:
        raise ValueError(f"{path.name}: missing front matter")
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        v = v.strip()
        meta[k.strip()] = None if v in ("", "null") else v
    return meta, m.group(2)


def load_chunks() -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(KB_DIR.glob("*.md")):
        meta, body = _parse_doc(path)
        pos = 0
        for block in re.split(r"(?m)^## ", body):
            block = block.strip()
            if not block:
                continue
            heading, _, content = block.partition("\n")
            words = content.split()
            for i in range(0, max(len(words), 1), MAX_WORDS):
                piece = " ".join(words[i : i + MAX_WORDS]).strip()
                if piece:
                    chunks.append({
                        "doc_id": meta["id"], "title": meta["title"], "section": heading.strip(),
                        "source_name": meta["source_name"], "source_url": meta.get("source_url"),
                        "review_status": meta.get("review_status") or "unreviewed", "text": piece, "position": pos,
                    })
                    pos += 1
    return chunks


_index_cache: dict = {"sig": None, "bm25": None, "chunks": None, "matrix": None}


def ensure_knowledge_base(db: Session | None = None) -> int:
    """Sync the DB with files in knowledge_base/. Keeps embeddings for unchanged chunks."""
    own = db is None
    db = db or SessionLocal()
    try:
        wanted = load_chunks()
        existing = {(c.doc_id, c.position): c for c in db.scalars(select(KnowledgeChunk))}
        unchanged = (
            len(existing) == len(wanted)
            and all((w["doc_id"], w["position"]) in existing and existing[(w["doc_id"], w["position"])].text == w["text"] for w in wanted)
        )
        if not unchanged:
            db.execute(delete(KnowledgeChunk))
            db.add_all(KnowledgeChunk(**w) for w in wanted)
            db.commit()
            _index_cache["sig"] = None
            log.info("Knowledge base rebuilt: %d chunks", len(wanted))
        return len(wanted)
    finally:
        if own:
            db.close()


def embed_missing(db: Session) -> int:
    """Create embeddings for chunks lacking one. Requires a configured Gemini key."""
    g = get_gemini()
    if not g.configured:
        return 0
    todo = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.embedding.is_(None))).all()
    if not todo:
        return 0
    vecs = g.embed([f"{c.title} – {c.section}\n{c.text}" for c in todo], task="RETRIEVAL_DOCUMENT")
    for c, v in zip(todo, vecs):
        c.embedding, c.embedding_model = v, g.embed_model
    db.commit()
    _index_cache["sig"] = None
    return len(todo)


# ---- retrieval ----------------------------------------------------------------------------------
def _tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in _STOP or len(w) < 2:
            continue
        for suf in ("ing", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


class _BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avgdl = sum(map(len, docs)) / max(len(docs), 1)
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in docs]

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for tf, d in zip(self.tf, self.docs):
            s = 0.0
            for t in set(query):
                f = tf.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / (self.avgdl or 1)))
            out.append(s)
        return out


def _index(db: Session):
    chunks = db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.doc_id, KnowledgeChunk.position)).all()
    sig = (len(chunks), sum(1 for c in chunks if c.embedding is not None))
    if _index_cache["sig"] != sig:
        _index_cache["bm25"] = _BM25([_tokens(f"{c.title} {c.section} {c.text}") for c in chunks])
        emb = [c.embedding for c in chunks]
        _index_cache["matrix"] = (
            np.array(emb, dtype=np.float32) if emb and all(e is not None for e in emb) else None
        )
        _index_cache["chunks"] = [
            Passage(c.id, c.title, c.section, c.text, c.source_name, c.source_url, c.review_status, 0.0) for c in chunks
        ]
        _index_cache["sig"] = sig
    return _index_cache["chunks"], _index_cache["bm25"], _index_cache["matrix"]


def retrieve(db: Session, query: str, k: int = 4, use_embeddings: bool = True) -> list[Passage]:
    chunks, bm25, matrix = _index(db)
    if not chunks:
        return []
    q_tokens = _tokens(query)
    bm = np.array(bm25.scores(q_tokens)) if q_tokens else np.zeros(len(chunks))
    rankings: list[np.ndarray] = []
    if bm.max() > 0:
        rankings.append(np.argsort(-bm))
    sem = None
    g = get_gemini()
    if use_embeddings and g.configured and matrix is not None:
        try:
            qv = np.array(g.embed([query], task="RETRIEVAL_QUERY")[0], dtype=np.float32)
            sem = (matrix @ qv) / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(qv) + 1e-9)
            rankings.append(np.argsort(-sem))
        except GeminiError as exc:
            log.warning("Embedding retrieval skipped: %s", exc)
    if not rankings:
        return []
    fused: Counter = Counter()
    for r in rankings:
        for rank, idx in enumerate(r[: k * 3]):
            fused[int(idx)] += 1.0 / (60 + rank)
    results = []
    for idx, score in fused.most_common(k):
        # relevance floor: needs a lexical hit or a decent semantic similarity
        relevant = bm[idx] > 0.8 or (sem is not None and sem[idx] > 0.55)
        if relevant:
            p = chunks[idx]
            results.append(Passage(p.id, p.title, p.section, p.text, p.source_name, p.source_url, p.review_status, float(score)))
    return results
