"""Download a verified source and build immutable, page-aware index versions."""

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import httpx
import numpy as np
from pypdf import PdfReader

from .config import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_DIM, EMBEDDING_MODEL, ROOT, SCHEMA_VERSION
from .embeddings import Embedder


def source_info():
    return json.loads((ROOT / "sources/prusa-mk4s.json").read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(settings):
    source = source_info()
    target = settings.data_dir / "raw" / source["filename"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256(target) == source["sha256"]:
        return target
    temporary = target.with_suffix(".part")
    try:
        with httpx.stream("GET", source["url"], follow_redirects=True, timeout=90) as response:
            response.raise_for_status()
            total = 0
            with temporary.open("wb") as file:
                for block in response.iter_bytes():
                    total += len(block)
                    if total > 64 * 1024 * 1024:
                        raise ValueError("Download exceeds the 64 MiB limit.")
                    file.write(block)
        if sha256(temporary) != source["sha256"]:
            raise ValueError(
                "Manual checksum changed. Review the official version before updating sources/prusa-mk4s.json."
            )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def chunk_page(text, page, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    if not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than chunk size.")
    lines = [line.strip() for line in text.splitlines()]
    text = " ".join(line for line in lines if line and not line.isdigit())
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary != -1:
                end = boundary
        content = text[start:end].strip()
        if content:
            chunks.append({"id": f"p{page:03d}-c{len(chunks) + 1:02d}", "page": page, "text": content})
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap)
        # Avoid starting halfway through a word when practical.
        boundary = text.find(" ", next_start, end)
        start = boundary + 1 if boundary != -1 else next_start
    return chunks


def build_index(settings):
    source = source_info()
    pdf = settings.data_dir / "raw" / source["filename"]
    if not pdf.exists():
        raise ValueError("Run python -m handbook download first.")
    if sha256(pdf) != source["sha256"]:
        raise ValueError("PDF checksum does not match the pinned source.")
    reader = PdfReader(pdf)
    if len(reader.pages) != source["pages"]:
        raise ValueError("Unexpected PDF page count.")
    print(f"Extracting text from {len(reader.pages)} PDF pages...", file=sys.stderr, flush=True)
    chunks = []
    for page, item in enumerate(reader.pages, 1):
        if page >= source["first_content_page"]:
            chunks.extend(chunk_page(item.extract_text() or "", page))
    if not chunks:
        raise ValueError("No extractable text; scanned PDFs need a separate OCR pipeline.")
    print(
        f"Loading embedding model for {len(chunks)} chunks (first run downloads weights)...",
        file=sys.stderr,
        flush=True,
    )
    model = Embedder(settings.data_dir / "cache")
    print("Embedding passages on CPU...", file=sys.stderr, flush=True)
    vectors = model.documents([chunk["text"] for chunk in chunks])
    if vectors.shape != (len(chunks), EMBEDDING_DIM):
        raise ValueError("Unexpected embedding dimensions.")
    indexes = settings.data_dir / "indexes"
    indexes.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".build-", dir=indexes))
    try:
        (staging / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        np.save(staging / "vectors.npy", vectors, allow_pickle=False)
        manifest = {
            "schema": SCHEMA_VERSION,
            "source": source,
            "embedding_model": EMBEDDING_MODEL,
            "dimension": EMBEDDING_DIM,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "chunk_count": len(chunks),
            "page_numbering": "physical PDF pages, starting at 1",
            "chunks_sha256": sha256(staging / "chunks.json"),
            "vectors_sha256": sha256(staging / "vectors.npy"),
        }
        version = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
        manifest["version"] = version
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        target = indexes / version
        if target.exists():
            shutil.rmtree(staging)
        else:
            staging.rename(target)
        pointer = indexes / "CURRENT.tmp"
        pointer.write_text(version, encoding="utf-8")
        os.replace(pointer, indexes / "CURRENT")
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)
