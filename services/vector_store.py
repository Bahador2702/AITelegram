import os
import pickle
import logging
import numpy as np
from config import VECTOR_STORE_DIR, CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available, vector search disabled")


class CourseVectorStore:
    def __init__(self, course_id: str):
        self.course_id = course_id
        self.store_dir = os.path.join(VECTOR_STORE_DIR, course_id)
        os.makedirs(self.store_dir, exist_ok=True)
        self.index_path = os.path.join(self.store_dir, "index.faiss")
        self.meta_path = os.path.join(self.store_dir, "metadata.pkl")
        self.index = None
        self.metadata: list[dict] = []
        self._load()

    def _load(self):
        if not FAISS_AVAILABLE:
            return
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.meta_path, "rb") as f:
                    self.metadata = pickle.load(f)
                logger.info(f"Loaded vector store for course {self.course_id}: {len(self.metadata)} chunks")
            except Exception as e:
                logger.error(f"Error loading vector store: {e}")
                self.index = None
                self.metadata = []

    def _save(self):
        if not FAISS_AVAILABLE or self.index is None:
            return
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.meta_path, "wb") as f:
                pickle.dump(self.metadata, f)
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")

    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]]):
        if not FAISS_AVAILABLE or not embeddings:
            return
        vectors = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(vectors)
        dim = vectors.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatIP(dim)
        self.index.add(vectors)
        self.metadata.extend(chunks)
        self._save()

    def search(self, query_embedding: list[float], k: int = 5, file_id: str | None = None) -> list[dict]:
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return []
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        scores, indices = self.index.search(query, min(k * 2, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            if file_id and meta.get("file_id") != file_id:
                continue
            results.append({**meta, "score": float(score)})
            if len(results) >= k:
                break
        return results

    def remove_file_chunks(self, file_id: str):
        if not self.metadata:
            return
        keep_indices = [i for i, m in enumerate(self.metadata) if m.get("file_id") != file_id]
        if len(keep_indices) == len(self.metadata):
            return
        if not FAISS_AVAILABLE or self.index is None:
            return
        new_metadata = [self.metadata[i] for i in keep_indices]
        if not new_metadata or not FAISS_AVAILABLE:
            self.index = None
            self.metadata = []
            self._save()
            return
        all_vectors = faiss.extract_index_ivf(self.index) if hasattr(faiss, "extract_index_ivf") else None
        self.metadata = new_metadata
        self._save()

    def get_all_text(self, file_id: str | None = None) -> str:
        chunks = self.metadata
        if file_id:
            chunks = [c for c in chunks if c.get("file_id") == file_id]
        return "\n\n".join(c.get("text", "") for c in chunks)

    def get_chunk_count(self) -> int:
        return len(self.metadata)

    def delete_store(self):
        import shutil
        if os.path.exists(self.store_dir):
            shutil.rmtree(self.store_dir)


_stores: dict[str, CourseVectorStore] = {}


def get_store(course_id: str) -> CourseVectorStore:
    if course_id not in _stores:
        _stores[course_id] = CourseVectorStore(course_id)
    return _stores[course_id]


def invalidate_store(course_id: str):
    if course_id in _stores:
        del _stores[course_id]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text.strip():
        return []
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        i += chunk_size - overlap
    return [c for c in chunks if len(c.strip()) > 50]
