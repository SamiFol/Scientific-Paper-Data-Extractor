"""RAG store: PDF -> page text -> chunks -> ChromaDB (persistent). Search returns chunks with file and page."""
import hashlib
import logging
import re
from pathlib import Path

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings
from pypdf import PdfReader

log = logging.getLogger("rag")

CHUNK_CHARS = 1000      # size of one chunk
OVERLAP = 150           # shared text between neighbouring chunks (keeps sentences from being cut off)
MIN_CHARS = 80          # smaller chunks (page numbers, headers) are noise
BATCH = 200


class HashEmbedding(EmbeddingFunction[Documents]):
    """Offline test embedding: hashed bag of words. Weak, only for tests or when the default model can't download."""

    def __init__(self, dim=256):
        self.dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        out = []
        for text in input:
            v = [0.0] * self.dim
            for w in re.findall(r"[a-z0-9]+", text.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out

    @staticmethod
    def name():
        return "hash-test"

    def get_config(self):
        return {"dim": self.dim}

    @staticmethod
    def build_from_config(config):
        return HashEmbedding(**config)


def extract_pages(pdf_path):
    """[(page_number, text)] with whitespace cleaned up and hyphenated line breaks joined."""
    pages = []
    for i, page in enumerate(PdfReader(str(pdf_path)).pages, 1):
        text = page.extract_text() or ""
        text = re.sub(r"-\n(?=[a-z])", "", text)
        pages.append((i, re.sub(r"\s+", " ", text).strip()))
    return pages


def chunk_text(text, size=CHUNK_CHARS, overlap=OVERLAP):
    """Split one page into ~size-char chunks that start and end at word boundaries."""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind(" ", start + size // 2, end)          # prefer a word boundary
            end = cut if cut != -1 else end
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
        nxt = text.find(" ", start, end)                           # start the next chunk at a word boundary
        start = nxt + 1 if nxt != -1 else start
    return [c for c in chunks if len(c) >= MIN_CHARS]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PaperIndex:
    def __init__(self, store_dir, embedding="default"):
        self.embedding = embedding
        self.client = chromadb.PersistentClient(path=str(store_dir), settings=Settings(anonymized_telemetry=False))
        kwargs = {"embedding_function": HashEmbedding()} if embedding == "hash" else {}
        # one collection per embedding type: vectors of different models must never be mixed
        self.col = self.client.get_or_create_collection(f"papers_{embedding}", metadata={"hnsw:space": "cosine"},
                                                        **kwargs)

    def _where(self, path):
        return {"source": str(Path(path).resolve())}

    def is_indexed(self, path):
        got = self.col.get(where=self._where(path), limit=1, include=["metadatas"])
        return bool(got["ids"]) and got["metadatas"][0].get("file_hash") == file_hash(path)

    def index_pdf(self, path):
        """Index one PDF (skipped if unchanged, replaced if the file changed). Returns a small report."""
        path = Path(path).resolve()
        if self.is_indexed(path):
            return {"name": path.name, "status": "already indexed", "chunks": self.count(path)}
        self.col.delete(where=self._where(path))
        h = file_hash(path)
        pages = extract_pages(path)
        empty = sum(1 for _, t in pages if len(t) < MIN_CHARS)
        ids, docs, metas = [], [], []
        for page_no, text in pages:
            for j, chunk in enumerate(chunk_text(text)):
                ids.append(f"{h[:12]}-p{page_no}-{j}")
                docs.append(chunk)
                metas.append({"source": str(path), "name": path.name, "page": page_no, "file_hash": h})
        if not ids:
            raise ValueError(f"{path.name} has no extractable text (scanned PDF? it needs OCR first)")
        for i in range(0, len(ids), BATCH):
            self.col.add(ids=ids[i:i + BATCH], documents=docs[i:i + BATCH], metadatas=metas[i:i + BATCH])
        log.info("indexed %s: %d pages, %d chunks", path.name, len(pages), len(ids))
        return {"name": path.name, "status": "indexed", "pages": len(pages), "chunks": len(ids),
                "pages_without_text": empty}

    def count(self, path=None):
        if path is None:
            return self.col.count()
        return len(self.col.get(where=self._where(path), include=[])["ids"])

    def search(self, query, k=5, path=None):
        """Top-k chunks, optionally only from one PDF. [{text, name, page, source, distance}] best first."""
        total = self.count(path)
        if not total:
            return []
        res = self.col.query(query_texts=[query], n_results=min(k, total),
                             where=self._where(path) if path else None)
        return [{"text": d, "name": m["name"], "page": m["page"], "source": m["source"], "distance": round(x, 4)}
                for d, m, x in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])]

    def indexed_sources(self):
        metas = self.col.get(include=["metadatas"])["metadatas"]
        return sorted({m["source"] for m in metas})