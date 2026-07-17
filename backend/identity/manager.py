"""
PersonSessionManager — coordinates PersonRegistry and PersonSessionState.

Responsibilities
----------------
- Owns the PersonRegistry (embedding matching).
- Creates/retrieves PersonSessionState for each detected person.
- Tracks the currently active person and enforces the grace window.
- Handles person-swap transitions: finalizes in-progress sets, switches
  active state.
- Provides the embedding extractor (InsightFace) as a background-safe
  callable so ws_pose.py can run it in a thread-pool executor.

Grace window
------------
If no face is detected for < GRACE_WINDOW_S seconds, the last confirmed
identity is held.  After that, the active person is set to None (waiting).
This prevents flickering when the person briefly looks away.

Thread safety
-------------
All methods are called from async coroutines in ws_pose.py.  The background
identification task (running in a thread-pool executor) writes to
_pending_person_id via asyncio.Queue — the main coroutine reads it on the
next frame to avoid data races.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import numpy as np

from backend.identity.registry import PersonRegistry
from backend.identity.session_state import PersonSessionState

logger = logging.getLogger(__name__)

# Grace window before "no face" is treated as "person left frame"
GRACE_WINDOW_S: float = 3.0

# Run face identification every N frames (~1.7s at 15fps)
IDENTIFY_EVERY_N_FRAMES: int = 25


class PersonSessionManager:
    """
    Top-level coordinator for automatic person identification.

    One instance lives for the lifetime of the WebSocket session.
    """

    def __init__(
        self,
        weight_kg: float = 70.0,
        height_cm: float = 0.0,
        similarity_threshold: float = 0.40,
    ) -> None:
        self._weight_kg = weight_kg
        self._height_cm = height_cm

        self._registry = PersonRegistry(similarity_threshold=similarity_threshold)
        self._states: dict[str, PersonSessionState] = {}  # person_id → state
        self._person_counter: int = 0

        # Currently active person
        self._active_id: Optional[str] = None
        self._last_face_seen_at: float = 0.0

        # Frame counter for throttled identification
        self._frame_count: int = 0

        # InsightFace app — loaded lazily on first call
        self._face_app = None
        self._face_app_loading = False

        # Thread-safe queue: background identification task posts results here
        self._id_queue: asyncio.Queue = asyncio.Queue(maxsize=2)

    # ------------------------------------------------------------------
    # Public interface called from ws_pose.py per frame
    # ------------------------------------------------------------------

    def tick(self, jpeg_bytes: bytes, loop: asyncio.AbstractEventLoop,
             executor) -> Optional[str]:
        """
        Called once per frame from the async pipeline.

        - Increments frame counter.
        - Every IDENTIFY_EVERY_N_FRAMES, schedules a background identification.
        - Drains any completed identification results from the queue.
        - Applies grace window to determine active_id.

        Returns the currently active person_id (may be None if no person
        confirmed yet or grace window expired).
        """
        self._frame_count += 1

        # Drain completed identification results (non-blocking)
        self._drain_id_queue()

        # Schedule identification if due
        if self._frame_count % IDENTIFY_EVERY_N_FRAMES == 1:
            asyncio.run_coroutine_threadsafe(
                self._identify_async(jpeg_bytes, loop, executor), loop
            )

        # Apply grace window
        now = time.time()
        if self._active_id is not None:
            elapsed_since_face = now - self._last_face_seen_at
            if elapsed_since_face > GRACE_WINDOW_S:
                logger.debug(
                    "Grace window expired (%.1fs); active person set to None",
                    elapsed_since_face,
                )
                # Finalize in-progress set before clearing
                if self._active_id in self._states:
                    state = self._states[self._active_id]
                    state.finalize_current_set(partial=True)
                self._active_id = None

        return self._active_id

    def get_active_state(self) -> Optional[PersonSessionState]:
        """Return the PersonSessionState for the currently active person."""
        if self._active_id is None:
            return None
        return self._states.get(self._active_id)

    def get_all_states(self) -> list[PersonSessionState]:
        """Return all known PersonSessionState instances (for History page)."""
        return list(self._states.values())

    def person_count(self) -> int:
        return len(self._states)

    # ------------------------------------------------------------------
    # Background identification
    # ------------------------------------------------------------------

    async def _identify_async(
        self, jpeg_bytes: bytes, loop: asyncio.AbstractEventLoop, executor
    ) -> None:
        """
        Run face detection + embedding extraction in the thread pool.
        Posts the result to _id_queue without blocking the event loop.
        """
        try:
            person_id = await loop.run_in_executor(
                executor, self._extract_and_match, jpeg_bytes
            )
            # Non-blocking put (drop if queue is full — stale result)
            if not self._id_queue.full():
                self._id_queue.put_nowait(person_id)
        except Exception as exc:
            logger.warning("Face identification failed: %s", exc)

    def _extract_and_match(self, jpeg_bytes: bytes) -> Optional[str]:
        """
        Synchronous: decode JPEG → detect face → extract embedding → match.
        Runs in a thread-pool executor, NOT on the event loop thread.

        Returns person_id if a face was found and matched/created.
        Returns None if no face detected.
        """
        import cv2
        import numpy as np

        app = self._get_face_app()
        if app is None:
            return None

        # Decode JPEG
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None

        # Detect faces and extract embeddings
        faces = app.get(frame)
        if not faces:
            return None

        # Use the largest face (closest to camera)
        largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        embedding = largest.embedding   # shape (512,), float32

        if embedding is None:
            return None

        return self._registry.identify(embedding)

    def _drain_id_queue(self) -> None:
        """Process any pending identification results from the queue."""
        while not self._id_queue.empty():
            try:
                person_id = self._id_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            if person_id is None:
                # Face not detected — grace window handles timeout
                continue

            self._last_face_seen_at = time.time()

            if person_id != self._active_id:
                self._handle_person_switch(person_id)
            else:
                # Same person — update last_seen
                if person_id in self._states:
                    self._states[person_id].last_seen_at = time.time()

    def _handle_person_switch(self, new_id: str) -> None:
        """
        Switch active person from current to new_id.

        1. Finalize in-progress set for outgoing person (partial=True).
        2. Create PersonSessionState for new_id if first seen.
        3. Set new_id as active.
        """
        # Finalize outgoing person's in-progress set
        if self._active_id and self._active_id in self._states:
            outgoing = self._states[self._active_id]
            finalized = outgoing.finalize_current_set(partial=True)
            if finalized:
                logger.info(
                    "Person swap: finalized partial set for %s "
                    "(exercise=%s, reps=%d, partial=True)",
                    outgoing.display_name, finalized.exercise, finalized.reps,
                )

        # Create state for new person if first seen
        if new_id not in self._states:
            self._person_counter += 1
            display_name = f"Person {self._person_counter}"
            state = PersonSessionState(
                person_id=new_id,
                display_name=display_name,
                weight_kg=self._weight_kg,
                height_cm=self._height_cm,
            )
            self._states[new_id] = state
            logger.info("New person detected: %s (%s)", display_name, new_id[:8])
        else:
            logger.info(
                "Person returned: %s (%s)",
                self._states[new_id].display_name, new_id[:8],
            )

        self._active_id = new_id
        self._states[new_id].last_seen_at = time.time()

    # ------------------------------------------------------------------
    # InsightFace lazy loader
    # ------------------------------------------------------------------

    def _get_face_app(self):
        """Return the InsightFace FaceAnalysis app, loading it if needed."""
        if self._face_app is not None:
            return self._face_app
        if self._face_app_loading:
            return None  # Still loading — skip this frame

        self._face_app_loading = True
        try:
            import insightface
            app = insightface.app.FaceAnalysis(
                name="buffalo_s",
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=0, det_size=(320, 320))
            self._face_app = app
            logger.info("InsightFace buffalo_s loaded for person identification.")
        except Exception as exc:
            logger.error("InsightFace failed to load: %s", exc)
            self._face_app = None
        finally:
            self._face_app_loading = False

        return self._face_app
