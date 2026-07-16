"""
TASK-3.3 — Nearest-person selection.

Selects the bounding box with the largest area (proxy for closest person).
"""

from typing import Optional


def select_nearest_person(
    boxes: list[tuple[float, float, float, float]],
) -> Optional[tuple[float, float, float, float]]:
    """
    Return the bounding box with the largest area.

    Args:
        boxes: List of normalised bounding boxes [(x1, y1, x2, y2)].

    Returns:
        The box with the largest (x2-x1)*(y2-y1) area, or None if list is empty.
        When only one box is present, returns it unchanged (no-op path).
    """
    if not boxes:
        return None
    if len(boxes) == 1:
        return boxes[0]

    def area(box: tuple[float, float, float, float]) -> float:
        x1, y1, x2, y2 = box
        return (x2 - x1) * (y2 - y1)

    return max(boxes, key=area)
