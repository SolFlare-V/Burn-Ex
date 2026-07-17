"""
PersonRegistry — in-memory face-embedding registry for session-scoped
person re-identification.

Design
------
- Uses 512-dimensional ArcFace embeddings produced by InsightFace buffalo_s.
- Identity is determined by cosine similarity between the new embedding and
  all stored embeddings.
- Cosine similarity ∈ [-1, 1]; for ArcFace embeddings of the same person
  it is typically > 0.35 in moderate conditions. Different people are
  typically < 0.25.
- Threshold of 0.40 chosen based on:
    • InsightFace docs and community benchmarks: same-person pairs on
      in-the-wild data average ~0.45-0.65; impostor pairs average ~0.1-0.2.
    • 0.40 sits in the gap and leaves a safety margin above the impostor mean.
    • Lower values risk identity merging; higher values risk fragmenting one
      person into multiple IDs under lighting or angle variation.
    • This is configurable — callers can pass a different threshold.
- Stored embedding for each person is the running mean of all matched
  embeddings seen so far, which makes the reference more robust over time
  (adapts to lighting changes, head angle variation within a session).

Limitations (communicate to judges)
------------------------------------
- Purely in-memory; does not persist across server restarts.
- First time a new person appears they have no stored embedding — they are
  assigned a new person_id immediately, and their embedding is stored on
  first detection.
- Under very low light or strong backlighting, InsightFace may not detect
  a face at all; the caller handles this via a grace window (hold last ID).
- Two people with similar appearance could theoretically be merged at the
  default threshold. In a controlled gym demo environment this is unlikely.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Default threshold — see module docstring for rationale
# ---------------------------------------------------------------------------
DEFAULT_SIMILARITY_THRESHOLD: float = 0.40


# ---------------------------------------------------------------------------
# PersonRecord
# ---------------------------------------------------------------------------

@dataclass
class PersonRecord:
    """
    All per-person state held by the registry.

    The embedding stored here is the running mean of all matched embeddings
    for this person in the current session.
    """
    person_id: str
    embedding: np.ndarray       # shape (512,), L2-normalised
    match_count: int = 1        # how many frames have matched this person


# ---------------------------------------------------------------------------
# PersonRegistry
# ---------------------------------------------------------------------------

class PersonRegistry:
    """
    Session-scoped in-memory registry for person re-identification.

    Usage
    -----
        registry = PersonRegistry()

        # Each time an embedding is extracted from a frame:
        person_id = registry.identify(embedding)

        # person_id is stable across frames for the same person.
        # A different person gets a different UUID.
    """

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        self._threshold = similarity_threshold
        self._records: dict[str, PersonRecord] = {}   # person_id → record

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def identify(self, embedding: np.ndarray) -> str:
        """
        Match *embedding* against all known persons.

        Returns the person_id of the best match if cosine similarity is at
        or above the threshold; otherwise creates a new person and returns
        their new person_id.

        Args:
            embedding: 512-dim float32 array from InsightFace recognize().
                       Does not need to be pre-normalised — this method
                       normalises it before comparison.

        Returns:
            A UUID string identifying the person.
        """
        norm_emb = _l2_normalise(embedding)

        best_id, best_sim = self._find_best_match(norm_emb)

        if best_id is not None and best_sim >= self._threshold:
            self._update_record(best_id, norm_emb)
            return best_id

        # No match — register as new person
        return self._register_new(norm_emb)

    def get_all_ids(self) -> list[str]:
        """Return all known person_ids in registration order."""
        return list(self._records.keys())

    def person_count(self) -> int:
        """Number of distinct persons seen this session."""
        return len(self._records)

    def reset(self) -> None:
        """Clear all records (e.g. on server restart)."""
        self._records.clear()

    def similarity_threshold(self) -> float:
        """The threshold used for matching decisions."""
        return self._threshold

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_best_match(
        self, norm_emb: np.ndarray
    ) -> tuple[Optional[str], float]:
        """
        Find the person with the highest cosine similarity to *norm_emb*.

        Returns (person_id, similarity) of the best match, or (None, 0.0)
        if the registry is empty.
        """
        best_id: Optional[str] = None
        best_sim: float = -1.0

        for pid, record in self._records.items():
            sim = float(np.dot(norm_emb, record.embedding))
            if sim > best_sim:
                best_sim = sim
                best_id = pid

        return best_id, best_sim

    def _update_record(self, person_id: str, norm_emb: np.ndarray) -> None:
        """
        Update the stored embedding for *person_id* using a running mean.

        Running mean makes the reference more robust to lighting / angle
        changes within a session without drifting too quickly.
        """
        rec = self._records[person_id]
        n = rec.match_count
        # Running mean: new_mean = (old_mean * n + new_emb) / (n + 1)
        updated = (rec.embedding * n + norm_emb) / (n + 1)
        rec.embedding = _l2_normalise(updated)
        rec.match_count += 1

    def _register_new(self, norm_emb: np.ndarray) -> str:
        """Create a new PersonRecord and return its UUID."""
        pid = str(uuid.uuid4())
        self._records[pid] = PersonRecord(
            person_id=pid,
            embedding=norm_emb.copy(),
            match_count=1,
        )
        return pid


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _l2_normalise(vec: np.ndarray) -> np.ndarray:
    """Return a L2-normalised copy of *vec*. Safe against zero vectors."""
    norm = np.linalg.norm(vec)
    if norm < 1e-10:
        return vec.copy()
    return vec / norm
