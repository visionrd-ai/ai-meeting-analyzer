"""
RAGManager — Chroma (local, persistent) with robust, meeting-aware chunking

Design goals
- Local-only Chroma with on-disk persistence (no Docker).
- True singleton: one shared client/embedding stack across your process.
- One collection per user to prevent cross-contamination of memory.
- Robust chunking for long meetings (1–2h) that respects sentence boundaries, adds overlap, and carries time metadata.

What’s new in this version
- Added `create_embeddings_from_segments(...)` to ingest structured transcripts like
  [{"text":..., "source":"System|Mic", "timestamp":"2025-11-03T12:33:40.394009"}, ...].
- Meeting-aware coalescing by small time gaps (e.g., ≤2.5s) to avoid mid-thought splits.
- Sentence-level splitting and token-budget packing with sentence overlap.
- Optional tiktoken-based token estimator; falls back to a fast heuristic.
"""
from __future__ import annotations

import os
import re
import time
import uuid
import math
import logging
import threading
import datetime as _dt
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set
from rag_helper import build_segments_from_double_space_transcript
try:
    import chromadb
    from chromadb import ClientAPI
    from chromadb.api.models.Collection import Collection
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except Exception as e:  # pragma: no cover
    raise ImportError(
        "chromadb is required. Install with: pip install chromadb sentence-transformers"
    ) from e

try:  # optional, for better token estimation
    import tiktoken  # type: ignore
    _HAS_TIKTOKEN = True
except Exception:  # pragma: no cover
    _HAS_TIKTOKEN = False


# -------------------------
# Configuration dataclasses
# -------------------------
@dataclass
class RAGConfig:
    persist_dir: str = os.path.abspath(os.getenv("RAG_CHROMA_DIR", ".chroma_rag"))
    default_model: str = os.getenv("RAG_EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")#all-MiniLM-L6-v2
    # Document/segment limits per user (tune in MemoryManagement)
    default_max_docs: int = int(os.getenv("RAG_DEFAULT_MAX_DOCS", "20000"))
    default_max_age_days: Optional[int] = None  # e.g., 90


# -------------------------
# Singleton implementation
# -------------------------
class _Singleton(type):
    _instance: Optional["RAGManager"] = None
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__call__(*args, **kwargs)
        return cls._instance


# -------------------------
# RAG Manager
# -------------------------
class RAGManager(metaclass=_Singleton):
    """Singleton wrapper around a local, persistent ChromaDB client.

    Responsibilities
    - Initialize Chroma (persistent) & embedding stack exactly once
    - Maintain per-user collections (no cross-user contamination)
    - Provide ingestion and query surfaces
    - Provide memory management utilities (prune by age/count)
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        embedding_model_name: Optional[str] = None,
    ) -> None:
        self.config = config or RAGConfig()
        self._client: ClientAPI = self._init_client(self.config.persist_dir)
        self._collections_cache: Dict[str, Collection] = {}
        self._user_limits: Dict[str, Tuple[int, Optional[int]]] = {}
        self._client_lock = threading.Lock()  # for reset operations / concurrency safety
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.setLevel(logging.INFO)

        # Embedding function (lazy configurable)
        model_name = embedding_model_name or self.config.default_model
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )
        self._log.info("RAGManager initialized (persist_dir=%s, model=%s)", self.config.persist_dir, model_name)

    # --------- internal utils ---------
    def _init_client(self, persist_dir: str) -> ClientAPI:
        os.makedirs(persist_dir, exist_ok=True)
        return chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

    def _collection_name_for_user(self, user_id: str) -> str:
        return f"user_{user_id}"

    def _get_or_create_user_collection(self, user_id: str) -> Collection:
        key = self._collection_name_for_user(user_id)
        if key in self._collections_cache:
            return self._collections_cache[key]

        try:
            col = self._client.get_collection(name=key)
        except Exception:
            col = self._client.create_collection(
                name=key,
                metadata={"scope": "user", "user_id": user_id},
                embedding_function=self._embedding_fn,
            )
        self._collections_cache[key] = col
        return col

    # ---- time helpers ----
    def _now_ts(self) -> float:
        return time.time()

    def _parse_iso_ts(self, s: str) -> float:
        """Parse ISO timestamp; naive datetimes are treated as local time."""
        dt = _dt.datetime.fromisoformat(s)
        return dt.timestamp()

    # ---- token & sentence helpers ----
    def _estimate_tokens(self, text: str) -> int:
        if _HAS_TIKTOKEN:
            try:
                enc = tiktoken.get_encoding("cl100k_base")
                return len(enc.encode(text))
            except Exception:
                pass
        # Fast heuristic: ~4 chars per token for English
        return max(1, math.ceil(len(text) / 4))

    def _split_sentences(self, text: str) -> List[str]:
        """Naive sentence splitter without regex to keep dependencies minimal.
        Splits on ., ?, ! when followed by a space or end-of-text. Keeps bracket tags like [Mic].
        """
        text = (text or "").strip()
        if not text:
            return []
        out: List[str] = []
        buf: List[str] = []
        n = len(text)
        i = 0
        while i < n:
            ch = text[i]
            buf.append(ch)
            end_punct = ch in ".?!"
            next_is_break = False
            if end_punct:
                j = i + 1
                if j >= n:
                    next_is_break = True
                else:
                    # allow close quotes/brackets before space
                    while j < n and text[j] in "])'\"»”} ":
                        if text[j] == " ":
                            next_is_break = True
                            break
                        j += 1
                    if j < n and text[j] == " ":
                        next_is_break = True
            if next_is_break:
                s = "".join(buf).strip()
                if s:
                    out.append(s)
                buf = []
            i += 1
        tail = "".join(buf).strip()
        if tail:
            out.append(tail)
        # Merge tiny fragments to neighbors
        merged: List[str] = []
        carry = ""
        for s in out:
            if self._estimate_tokens(s) < 8:
                carry = (carry + " " + s).strip()
            else:
                if carry:
                    merged.append(carry)
                    carry = ""
                merged.append(s)
        if carry:
            merged.append(carry)
        return merged

    def _chunk_sentences_by_token_budget(
        self,
        sentences: List[Tuple[str, float, float, Set[str]]],
        *,
        max_tokens: int = 350,
        sentence_overlap: int = 2,
    ) -> List[Tuple[str, float, float, Set[str]]]:
        """Pack sentences into chunks under a token budget, with overlap.
        Returns list of (chunk_text, start_ts, end_ts, sources).
        """
        chunks: List[Tuple[str, float, float, Set[str]]] = []
        i = 0
        while i < len(sentences):
            buf: List[str] = []
            buf_tokens = 0
            start_ts = sentences[i][1]
            sources: Set[str] = set()
            j = i
            end_ts = sentences[i][2]
            while j < len(sentences):
                sent, s_ts, e_ts, s_sources = sentences[j]
                t = self._estimate_tokens(sent)
                if buf and buf_tokens + t > max_tokens:
                    break
                buf.append(sent)
                buf_tokens += t
                sources.update(s_sources)
                end_ts = e_ts
                j += 1
            if not buf:  # sentence longer than budget; hard cut
                sent, s_ts, e_ts, s_sources = sentences[j]
                buf = [sent]
                start_ts = s_ts
                end_ts = e_ts
                sources = set(s_sources)
                j += 1
            chunks.append((" ".join(buf), start_ts, end_ts, sources))
            # advance with overlap
            if sentence_overlap > 0:
                i = max(i + 1, j - sentence_overlap)
            else:
                i = j
        return chunks

    # ---- segment coalescing for meetings ----
    def _coalesce_segments(
        self,
        segments: List[Dict[str, Any]],
        *,
        max_gap_seconds: float = 2.5,
    ) -> List[Dict[str, Any]]:
        """Coalesce small-gap transcript items into larger utterances.
        Each input: {"text": str, "source": "System|Mic"|..., "timestamp": ISO str}
        Output item: {"text": "[Src] ... [Src] ...", "start_ts": float, "end_ts": float, "sources": set[str]}
        """
        if not segments:
            return []
        # sort by timestamp
        norm = []
        for seg in segments:
            try:
                ts = self._parse_iso_ts(str(seg.get("timestamp")))
            except Exception:
                ts = self._now_ts()
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            src = str(seg.get("source", "System")).strip() or "System"
            norm.append((ts, src, text))
        norm.sort(key=lambda x: x[0])

        out: List[Dict[str, Any]] = []
        cur_text_parts: List[str] = []
        cur_start = norm[0][0]
        cur_end = norm[0][0]
        cur_sources: Set[str] = set()
        last_ts = norm[0][0]

        def _flush():
            if not cur_text_parts:
                return
            out.append({
                "text": " ".join(cur_text_parts).strip(),
                "start_ts": cur_start,
                "end_ts": cur_end,
                "sources": set(cur_sources),
            })

        for ts, src, text in norm:
            gap = ts - last_ts
            prefix = "[" + src + "] "
            if gap <= max_gap_seconds and cur_text_parts:
                # Continue same utterance
                cur_text_parts.append(prefix + text)
                cur_end = ts
                cur_sources.add(src)
            else:
                # New utterance
                if cur_text_parts:
                    _flush()
                cur_text_parts = [prefix + text]
                cur_start = ts
                cur_end = ts
                cur_sources = {src}
            last_ts = ts
        _flush()
        return out

    def _sentences_from_segments(
        self,
        segments: List[Dict[str, Any]],
        *,
        max_gap_seconds: float = 2.5,
    ) -> List[Tuple[str, float, float, Set[str]]]:
        """Produce sentence tuples (text, start_ts, end_ts, sources) from segments."""
        utterances = self._coalesce_segments(segments, max_gap_seconds=max_gap_seconds)
        sentences: List[Tuple[str, float, float, Set[str]]] = []
        for utt in utterances:
            text = utt["text"].strip()
            s_ts = float(utt["start_ts"])  # may be equal to end_ts when single point
            e_ts = float(utt["end_ts"]) if float(utt["end_ts"]) >= s_ts else s_ts
            srcs: Set[str] = set(utt.get("sources", set()))
            for sent in self._split_sentences(text):
                if not sent:
                    continue
                sentences.append((sent, s_ts, e_ts, set(srcs)))
        return sentences

        # --------- metadata safety helper ---------
    def _safe_chunk_metadata(
        self,
        user_id: str,
        session_id: str,
        start_ts: float,
        end_ts: float,
        srcs,
        extra_metadata: Optional[dict] = None,
    ) -> dict:
        srcs = set(srcs or [])
        source_list = sorted(srcs)
        md = {
            "user_id": user_id,
            "session_id": session_id,
            "start_ts": float(start_ts),
            "end_ts": float(end_ts),
            # primitives only for Chroma metadata
            "source_primary": (source_list[0] if len(source_list) == 1 else "Mixed"),
            "source_is_mic": ("Mic" in srcs),
            "source_is_system": ("System" in srcs),
            "sources_csv": ",".join(source_list),
            "type": "meeting_transcript_chunk",
        }
        if extra_metadata:
            for k, v in extra_metadata.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    md[k] = v
                else:
                    md[k] = str(v)
        return md

    # --------- persistence hint ---------
    def persist(self) -> None:
        """Force fs sync (no-op for PersistentClient, here for API symmetry)."""
        self._log.debug("Persist called (PersistentClient writes on the fly)")

    # --------- public API: ingestion ---------
    def create_embeddings_from_transcription(
        self,
        user_id: str,
        session_id: str,
        transcription: str,
        *,
        chunk_token_budget: int = 350,
        sentence_overlap: int = 2,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingest a raw transcription string. Uses sentence-aware, token-budgeted chunks.
        Prefer `create_embeddings_from_segments` when timestamps are available.
        """
        col = self._get_or_create_user_collection(user_id)
        sents_raw = self._split_sentences(transcription)
        # lift into (sent, start_ts, end_ts, sources) with synthetic timestamps
        now = self._now_ts()
        sents = [(s, now, now, {"Unknown"}) for s in sents_raw]
        chunks = self._chunk_sentences_by_token_budget(
            sents, max_tokens=chunk_token_budget, sentence_overlap=sentence_overlap
        )
        if not chunks:
            return {"added": 0, "collection": col.name}

        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = []
        docs = []
        for text, s_ts, e_ts, srcs in chunks:
            md = self._safe_chunk_metadata(
                user_id=user_id,
                session_id=session_id,
                start_ts=s_ts,
                end_ts=e_ts,
                srcs=srcs,
                extra_metadata=extra_metadata,
            )
            metadatas.append(md)
            docs.append(text)

        col.upsert(ids=ids, documents=docs, metadatas=metadatas)
        self._log.info("Ingested %d chunks (string) for user=%s session=%s", len(docs), user_id, session_id)
        self.memory_management(user_id)
        return {"added": len(docs), "collection": col.name}

    def create_embeddings_from_segments(
        self,
        user_id: str,
        session_id: str,
        segments: List[Dict[str, Any]],
        *,
        chunk_token_budget: int = 350,
        sentence_overlap: int = 2,
        max_gap_seconds: float = 2.5,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingest a meeting transcript represented as a list of {text, source, timestamp}.

        Strategy
        1) Sort & coalesce by small inter-item gaps (≤max_gap_seconds) to avoid mid-thought splits.
        2) Split utterances to sentences.
        3) Pack sentences into chunks under `chunk_token_budget`, with `sentence_overlap` between chunks.
        4) Persist chunks with [start_ts, end_ts, sources] metadata.
        """
        col = self._get_or_create_user_collection(user_id)
        sentences = self._sentences_from_segments(segments, max_gap_seconds=max_gap_seconds)
        chunks = self._chunk_sentences_by_token_budget(
            sentences, max_tokens=chunk_token_budget, sentence_overlap=sentence_overlap
        )
        if not chunks:
            return {"added": 0, "collection": col.name}

        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = []
        docs = []
        for text, s_ts, e_ts, srcs in chunks:
            md = self._safe_chunk_metadata(
                user_id=user_id,
                session_id=session_id,
                start_ts=s_ts,
                end_ts=e_ts,
                srcs=srcs,
                extra_metadata=extra_metadata,
            )
            metadatas.append(md)
            docs.append(text)

        col.upsert(ids=ids, documents=docs, metadatas=metadatas)
        self._log.info(
            "Ingested %d chunks (segments) for user=%s session=%s [budget=%s, overlap=%s]",
            len(docs), user_id, session_id, chunk_token_budget, sentence_overlap,
        )
        self.memory_management(user_id)
        return {"added": len(docs), "collection": col.name}

    # --------- public API: retrieval ---------
    # --- retrieval helpers (scoring & MMR) ---
    _STOPWORDS = {
        "the","a","an","and","or","but","if","then","so","to","of","in","on","for","by","with","at","as","it","is","are","was","were","be","this","that","these","those","we","you","i","our","your","their","from"
    }

    def _tok(self, text: str) -> List[str]:
        text = (text or "").lower()
        # keep alphanum words
        return [w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", text) if w not in self._STOPWORDS]

    def _keyword_score(self, doc: str, q_tokens: List[str]) -> float:
        if not doc or not q_tokens:
            return 0.0
        dset = set(self._tok(doc))
        if not dset:
            return 0.0
        inter = len(dset.intersection(q_tokens))
        return inter / max(1, len(q_tokens))

    def _mmr(self, cand_vecs: List[List[float]], base_scores: List[float], k: int, lam: float = 0.7) -> List[int]:
        """Return indices selected by Maximal Marginal Relevance (assumes vectors are L2-normalized)."""
        if not cand_vecs:
            return []
        import math
        n = len(cand_vecs)
        selected: List[int] = []
        remaining = set(range(n))
        # seed with best base score
        seed = max(remaining, key=lambda i: base_scores[i])
        selected.append(seed)
        remaining.remove(seed)
        while remaining and len(selected) < k:
            best_i = None
            best_val = -1e9
            for i in list(remaining):
                # similarity to selected = max dot(selected, i)
                sim_sel = 0.0
                for j in selected:
                    # cosine = dot since normalized
                    v = sum(a*b for a,b in zip(cand_vecs[i], cand_vecs[j]))
                    if v > sim_sel:
                        sim_sel = v
                val = lam * base_scores[i] - (1.0 - lam) * sim_sel
                if val > best_val:
                    best_val = val
                    best_i = i
            selected.append(best_i)
            remaining.remove(best_i)
        return selected

    def retrieve_query_results(
        self,
        user_message: str,
        user_id: str,
        *,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        max_distance: Optional[float] = None,
        include: Tuple[str, ...] = ("documents", "metadatas", "distances"),
    ) -> Dict[str, Any]:
        col = self._get_or_create_user_collection(user_id)
        res = col.query(query_texts=[user_message], n_results=k, where=where, include=list(include))

        # Optional: apply a client-side distance threshold filter
        if max_distance is not None and "distances" in res:
            pruned = {k: [] for k in res}
            for i in range(len(res.get("ids", [[]])[0])):
                dist = res["distances"][0][i]
                if dist <= max_distance:
                    for key in res:
                        pruned.setdefault(key, [])
                        pruned[key].append(res[key][0][i])
            for key in pruned:
                pruned[key] = [pruned[key]]
            res = pruned
        return res

    def retrieve_query_results_smart(
        self,
        user_message: str,
        user_id: str,
        *,
        k: int = 5,
        k_initial: int = 24,
        session_id: Optional[str] = None,
        time_window_sec: Optional[int] = None,
        prefer_recent: bool = True,
        keyword_boost: float = 0.5,
        mmr_lambda: float = 0.7,
    ) -> Dict[str, Any]:
        """Improved retrieval: dense + keyword boosting + optional time bias + MMR de-dup/diversity.
        Returns the same shape as Chroma's query().
        """
        col = self._get_or_create_user_collection(user_id)

        # Build where filter
        where: Dict[str, Any] = {"user_id": user_id}
        if session_id:
            where["session_id"] = session_id
        if isinstance(time_window_sec, int) and time_window_sec > 0:
            cutoff = self._now_ts() - float(time_window_sec)
            where["end_ts"] = {"$gt": cutoff}

        res = col.query(
            query_texts=[user_message],
            n_results=max(k, k_initial),
            where=where,
            include=["documents", "metadatas", "distances", "embeddings"],
        )

        ids = (res.get("ids", [[]]) or [[]])[0]
        docs = (res.get("documents", [[]]) or [[]])[0]
        metas = (res.get("metadatas", [[]]) or [[]])[0]
        dists = (res.get("distances", [[]]) or [[]])[0]
        embeds = (res.get("embeddings", [[]]) or [[]])[0]

        # De-duplicate identical docs (keep best distance)
        best: Dict[str, int] = {}
        for i, doc in enumerate(docs):
            if doc not in best:
                best[doc] = i
            else:
                prev = best[doc]
                if dists[i] < dists[prev]:
                    best[doc] = i
        keep_idx = sorted(best.values(), key=lambda i: dists[i])

        # Compute scores
        q_tokens = self._tok(user_message)
        sims = [1.0 - dists[i] if isinstance(dists[i], (int, float)) else 0.0 for i in keep_idx]
        kw = [self._keyword_score(docs[i], q_tokens) for i in keep_idx]

        # recency bonus (optional)
        now = self._now_ts()
        def _recency(m):
            try:
                age = max(0.0, now - float(m.get("end_ts") or m.get("start_ts") or now))
            except Exception:
                age = 0.0
            # exponential decay over ~2 hours
            return math.exp(-age / 7200.0) if prefer_recent else 0.0
        rec = [_recency(metas[i]) for i in keep_idx]

        base = [s + keyword_boost * k + 0.15 * r for s, k, r in zip(sims, kw, rec)]

        # MMR selection using embeddings
        cand_vecs = [embeds[i] for i in keep_idx]
        sel_rel = self._mmr(cand_vecs, base, k=k, lam=mmr_lambda) if cand_vecs else list(range(min(k, len(keep_idx))))
        final_idx = [keep_idx[i] for i in sel_rel]

        # Assemble result in Chroma shape
        out = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]], "embeddings": [[]], "included": ["documents","metadatas","distances","embeddings"], "uris": None, "data": None}
        for i in final_idx:
            out["ids"][0].append(ids[i])
            out["documents"][0].append(docs[i])
            out["metadatas"][0].append(metas[i])
            out["distances"][0].append(dists[i])
            out["embeddings"][0].append(embeds[i])
        return out
    def retrieve_query_results(
        self,
        user_message: str,
        user_id: str,
        *,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        max_distance: Optional[float] = None,
        include: Tuple[str, ...] = ("documents", "metadatas", "distances"),
    ) -> Dict[str, Any]:
        col = self._get_or_create_user_collection(user_id)
        res = col.query(query_texts=[user_message], n_results=k, where=where, include=list(include))

        # Optional: apply a client-side distance threshold filter
        if max_distance is not None and "distances" in res:
            pruned = {k: [] for k in res}
            for i in range(len(res.get("ids", [[]])[0])):
                dist = res["distances"][0][i]
                if dist <= max_distance:
                    for key in res:
                        pruned.setdefault(key, [])
                        pruned[key].append(res[key][0][i])
            for key in pruned:
                pruned[key] = [pruned[key]]
            res = pruned
        return res

    # --------- public API: memory mgmt ---------
    def memory_management(
        self,
        user_id: str,
        *,
        max_docs: Optional[int] = None,
        max_age_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        col = self._get_or_create_user_collection(user_id)

        # Resolve limits
        if user_id in self._user_limits:
            default_docs, default_age = self._user_limits[user_id]
        else:
            default_docs, default_age = self.config.default_max_docs, self.config.default_max_age_days

        max_docs = max_docs if max_docs is not None else default_docs
        max_age_days = max_age_days if max_age_days is not None else default_age

        deleted_by_age = 0
        deleted_by_count = 0

        # 1) Age pruning via server-side filter
        if isinstance(max_age_days, int) and max_age_days > 0:
            cutoff = self._now_ts() - (max_age_days * 86400)
            try:
                deleted = col.delete(where={"user_id": user_id, "end_ts": {"$lt": cutoff}})
                deleted_by_age = len(deleted) if isinstance(deleted, list) else 0
            except Exception as e:
                self._log.warning("Age pruning skipped (reason: %s)", e)

        # 2) Count pruning (client-side ordering by start_ts)
        records = col.get(where={"user_id": user_id}, include=["metadatas"]) 
        ids = records.get("ids", [])
        metas = records.get("metadatas", [])
        if ids and metas and isinstance(max_docs, int) and max_docs > 0:
            items = [((m.get("end_ts") or m.get("start_ts") or 0.0), i) for i, m in enumerate(metas)]
            items.sort(key=lambda t: t[0], reverse=True)
            if len(items) > max_docs:
                to_drop_idx = [idx for _, idx in items[max_docs:]]
                to_drop_ids = [ids[i] for i in to_drop_idx]
                if to_drop_ids:
                    col.delete(ids=to_drop_ids)
                    deleted_by_count = len(to_drop_ids)

        report = {
            "collection": col.name,
            "deleted_by_age": deleted_by_age,
            "deleted_by_count": deleted_by_count,
            "kept_docs": col.count(),
        }
        self._log.info("Prune report (%s): %s", user_id, report)
        return report

    # --------- optional helpers ---------
    def set_user_limits(self, user_id: str, *, max_docs: Optional[int] = None, max_age_days: Optional[int] = None) -> None:
        current = self._user_limits.get(user_id, (self.config.default_max_docs, self.config.default_max_age_days))
        new_docs = max_docs if max_docs is not None else current[0]
        new_age = max_age_days if max_age_days is not None else current[1]
        self._user_limits[user_id] = (new_docs, new_age)

    def delete_session(self, user_id: str, session_id: str) -> int:
        col = self._get_or_create_user_collection(user_id)
        try:
            deleted = col.delete(where={"user_id": user_id, "session_id": session_id})
            return len(deleted) if isinstance(deleted, list) else 0
        except Exception:
            return 0

    def drop_user_memory(self, user_id: str) -> None:
        key = self._collection_name_for_user(user_id)
        try:
            self._client.delete_collection(key)
        finally:
            self._collections_cache.pop(key, None)

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        col = self._get_or_create_user_collection(user_id)
        ids = col.get(include=["ids"]).get("ids", [])
        return {"collection": col.name, "doc_count": len(ids)}

    def list_users(self) -> List[str]:
        users: List[str] = []
        for col in self._client.list_collections():
            if col.name.startswith("user_"):
                users.append(col.name.replace("user_", "", 1))
        return users

    # --------- admin/reset helpers ---------
    def reset_vector_db(self, *, hard: bool = False) -> Dict[str, Any]:
        """Delete all collections (soft). If hard=True, also wipe the persistence folder and reinit client.
        Returns a small report. Use carefully in tests.
        """
        with self._client_lock:
            # Soft reset: delete all collections via API
            names = []
            try:
                for col in list(self._client.list_collections()):
                    names.append(col.name)
                    try:
                        self._client.delete_collection(col.name)
                    except Exception:
                        pass
            finally:
                self._collections_cache.clear()

            report = {"deleted_collections": names, "persist_dir": self.config.persist_dir, "hard": bool(hard)}

            if hard:
                # Hard reset: remove on-disk data and re-create client
                import shutil
                try:
                    shutil.rmtree(self.config.persist_dir, ignore_errors=True)
                except Exception:
                    pass
                os.makedirs(self.config.persist_dir, exist_ok=True)
                # Reinitialize client (embedding fn remains unchanged)
                self._client = self._init_client(self.config.persist_dir)

            return report


    # --------- verbatim ingestion (no packing) ---------
    def create_embeddings_from_segments_verbatim(
        self,
        user_id: str,
        session_id: str,
        segments: List[Dict[str, Any]],
        *,
        seconds_per_word: float = 0.32,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store one document per *input* segment. No coalescing, no sentence packing.
        Useful for precise tests where each provided segment must be its own chunk.
        """
        col = self._get_or_create_user_collection(user_id)
        docs: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            try:
                s_ts = self._parse_iso_ts(str(seg.get("timestamp")))
            except Exception:
                s_ts = self._now_ts()
            duration = max(1, len(text.split())) * seconds_per_word
            e_ts = s_ts + float(duration)
            src = str(seg.get("source") or "System")
            md = self._safe_chunk_metadata(
                user_id=user_id,
                session_id=session_id,
                start_ts=float(s_ts),
                end_ts=float(e_ts),
                srcs={src},
                extra_metadata=extra_metadata,
            )
            docs.append(text)
            metadatas.append(md)
            ids.append(str(uuid.uuid4()))

        if not docs:
            return {"added": 0, "collection": col.name}

        col.upsert(ids=ids, documents=docs, metadatas=metadatas)
        self._log.info("Ingested %d chunks (mode=per_segment) for user=%s session=%s", len(docs), user_id, session_id)
        self.memory_management(user_id)
        return {"added": len(docs), "collection": col.name}

    def ingest_segments_verbatim(self, user_id: str, session_id: str, segments: List[Dict[str, Any]], *, seconds_per_word: float = 0.32, extra_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.create_embeddings_from_segments_verbatim(user_id=user_id, session_id=session_id, segments=segments, seconds_per_word=seconds_per_word, extra_metadata=extra_metadata)

# -------------------------
# Example usage (remove in prod)
# -------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rag = RAGManager()
    uid = "alice"
    sid = "meeting-124"

    # -------- Pretty output helpers for Chroma --------
    import datetime as _dt
    from typing import Any, Dict, List, Optional
    from textwrap import shorten

    def _fmt_ts(ts: Optional[float], tz: str = "Asia/Karachi") -> str:
        if ts is None:
            return "—"
        try:
            from zoneinfo import ZoneInfo  # py>=3.9
            return _dt.datetime.fromtimestamp(float(ts), ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return _dt.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")

    def format_chroma_query_result(
        res: Dict[str, Any],
        *,
        max_chars: int = 180,
        tz: str = "Asia/Karachi"
    ) -> str:
        """Return a human-readable string for Chroma query() results."""
        lines: List[str] = []
        q_count = len(res.get("ids", [])) or 1

        for q in range(q_count):
            ids = (res.get("ids", [[]]) or [[]])[q] or []
            docs = (res.get("documents", [[]]) or [[]])[q] or []
            metas = (res.get("metadatas", [[]]) or [[]])[q] or []
            dists = (res.get("distances", [[]]) or [[]])[q] or []

            k = max(len(ids), len(docs), len(metas), len(dists))
            lines.append(f"Top results for query {q+1} (k={k}):")

            for i in range(k):
                id_ = ids[i] if i < len(ids) else "—"
                doc = docs[i] if i < len(docs) else ""
                md = metas[i] if i < len(metas) else {}
                dist = dists[i] if i < len(dists) else None
                sim = (1 - dist) if isinstance(dist, (int, float)) else None
                sim_str = f"{sim*100:.1f}%" if sim is not None else "—"
                dist_str = f"{dist:.3f}" if isinstance(dist, (int, float)) else "—"

                preview = shorten((doc or "").replace("\n", " "), width=max_chars, placeholder=" …")
                start_ts, end_ts = md.get("start_ts"), md.get("end_ts")
                when = f"{_fmt_ts(start_ts, tz)} → {_fmt_ts(end_ts, tz)}"

                src = md.get("source_primary") or md.get("sources_csv") or "Unknown"
                session = md.get("session_id") or "—"

                lines.append(
                    f"{i+1}. id={id_}\n"
                    f"   similarity={sim_str} (1 - distance={dist_str})   session={session}   src={src}\n"
                    f"   window={when}\n"
                    f"   text: {preview}"
                )
        return "\n".join(lines)

    def print_chroma_query_result(res: Dict[str, Any], **kwargs) -> None:
        print(format_chroma_query_result(res, **kwargs))

    def format_prune_report(report: Dict[str, Any]) -> str:
        return (
            f"Collection: {report.get('collection','—')}\n"
            f"Deleted by age: {report.get('deleted_by_age', 0)}\n"
            f"Deleted by count: {report.get('deleted_by_count', 0)}\n"
            f"Kept docs: {report.get('kept_docs', '—')}"
        )


    # Ingest structured segments
    # segments = [
    #     {"text": "We finally have a stable prototype running on the new glasses.", "source": "System", "timestamp": "2025-11-06T13:51:31.000000"},
    #     {"text": "The demos went well but latency spikes are still noticeable under load.", "source": "System", "timestamp": "2025-11-06T13:51:36.000000"},
    #     {"text": "Battery life improved by twelve percent after the encoder patch.", "source": "System", "timestamp": "2025-11-06T13:51:40.000000"},
    #     {"text": "Privacy is non-negotiable; on-device transcription stays on by default.", "source": "System", "timestamp": "2025-11-06T13:51:45.000000"},
    #     {"text": "For the beta we’ll gate the computer-vision features behind a toggle.", "source": "System", "timestamp": "2025-11-06T13:51:50.000000"},
    #     {"text": "The launch workflows we will support are onboarding walkthroughs, hands-free assistance, and real-time debugging hints.", "source": "System", "timestamp": "2025-11-06T13:51:55.000000"},
    #     {"text": "Guided mode should auto-explain what the user is seeing without interrupting them.", "source": "System", "timestamp": "2025-11-06T13:52:00.000000"},
    #     {"text": "We’ll ship a fallback that caches prompts offline and syncs when back online.", "source": "System", "timestamp": "2025-11-06T13:52:05.000000"},
    #     {"text": "Customer success asked for a safety checklist before each recording session.", "source": "System", "timestamp": "2025-11-06T13:52:10.000000"},
    #     {"text": "Post-meeting, we’ll generate action items and a short timeline summary.", "source": "System", "timestamp": "2025-11-06T13:52:15.000000"},
    #     {"text": "If adoption is strong in week one, we add multilingual captions in week two.", "source": "System", "timestamp": "2025-11-06T13:52:19.000000"},
    #     {"text": "Marketing wants a simple pricing page and a one-minute explainer video.", "source": "System", "timestamp": "2025-11-06T13:52:22.000000"},
    # ]

    # report = rag.create_embeddings_from_segments(
    #     user_id=uid,
    #     session_id=sid,
    #     segments=segments,
    #     chunk_token_budget=50,
    #     sentence_overlap=1,
    #     max_gap_seconds=0.6,
    # )
    # # report = rag.ingest_segments_verbatim(
    # #     user_id=uid,
    # #     session_id=sid,
    # #     segments=segments,
    # #     seconds_per_word=0.32,
    # # )
    # print("INGEST (segments):", report)

#     transcript = (
#     "We finally have a stable prototype running on the new glasses.  "
#     "The demos went well but latency spikes are still noticeable under load.  "
#     "Battery life improved by twelve percent after the encoder patch.  "
#     "Privacy is non-negotiable; on-device transcription stays on by default.  "
#     "For the beta we’ll gate the computer-vision features behind a toggle.  "
#     "The launch workflows we will support are onboarding walkthroughs, hands-free assistance, and real-time debugging hints.  "
#     "Guided mode should auto-explain what the user is seeing without interrupting them.  "
#     "We’ll ship a fallback that caches prompts offline and syncs when back online.  "
#     "Customer success asked for a safety checklist before each recording session.  "
#     "Post-meeting, we’ll generate action items and a short timeline summary.  "
#     "If adoption is strong in week one, we add multilingual captions in week two.  "
#     "Marketing wants a simple pricing page and a one-minute explainer video."
# )
    transcript_lines_broken = """[System]
    We finally have a stable prototype running on the new glasses. The demos went well but latency spikes are still noticeable under load. Battery life improved by twelve percent after the encoder patch.

    [System]
    Privacy is non-negotiable; on-device transcription stays on by default. For the beta we’ll gate the computer-vision features behind a toggle. The launch workflows we will support are onboarding walkthroughs, hands-free assistance, and real-time debugging hints.

    [System]
    Guided mode should auto-explain what the user is seeing without interrupting them. We’ll ship a fallback that caches prompts offline and syncs when back online.

    [System]
    Customer success asked for a safety checklist before each recording session. Post-meeting, we’ll generate action items and a short timeline summary. If adoption is strong in week one, we add multilingual captions in week two. Marketing wants a simple pricing page and a one-minute explainer video.
    """

    # Ingest raw transcription
    segments = build_segments_from_double_space_transcript(transcript_lines_broken)
    report = rag.create_embeddings_from_segments(
        user_id=uid,
        session_id=sid,
        segments=segments,
        chunk_token_budget=50,
        sentence_overlap=2,
        max_gap_seconds=1,
    )

    print("INGEST (raw):", report)

    query_easy = "Which launch workflows are we supporting at launch?"
    query_hard = "What are the launch workflows we will support: onboarding, hands-free assistance, and real-time debugging?"

    # Query 1
    # out = rag.retrieve_query_results(user_message=query_easy, user_id=uid, k=3)
    out = rag.retrieve_query_results_smart(user_message=query_easy, user_id=uid,     
                                            k=5, k_initial=32,
                                            time_window_sec=None,
                                            keyword_boost=1.0,
                                            mmr_lambda=0.6
                                        )
    print_chroma_query_result(out, max_chars=160, tz="Asia/Karachi")

    # Query 2
    out = rag.retrieve_query_results_smart(user_message=query_hard, user_id=uid, 
                                            k=5, k_initial=32,
                                            time_window_sec=None,
                                            keyword_boost=1.0,
                                            mmr_lambda=0.6
                                        )
    print_chroma_query_result(out, max_chars=160, tz="Asia/Karachi")
   
   
    # Memory management / Prune
    prune = rag.memory_management(user_id=uid)
    print(format_prune_report(prune))

    rag.reset_vector_db(hard=False)