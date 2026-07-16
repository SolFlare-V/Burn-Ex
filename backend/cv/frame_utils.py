"""
TASK-3.4 — Frame cropping with padding.

Crops a frame to a bounding-box ROI with 10% padding on all sides,
clamped to frame boundaries.
"""

import numpy as np


def crop_with_padding(
    frame: np.ndarray,
    box: tuple[float, float, float, float],
    padding: float = 0.10,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """
    Crop frame to the ROI defined by normalised bounding box with padding.

    Args:
        frame: numpy array of shape (H, W, C), uint8.
        box:   Normalised bounding box (x1, y1, x2, y2) in [0, 1].
        padding: Fractional padding to add on each side (default 0.10 = 10%).

    Returns:
        A tuple of (cropped_frame, (px1_px, py1_px, px2_px, py2_px))
    """
    if frame is None or frame.size == 0:
        return frame, (0, 0, 0, 0)

    h, w = frame.shape[:2]
    x1_n, y1_n, x2_n, y2_n = box

    bw = x2_n - x1_n  # normalised box width
    bh = y2_n - y1_n  # normalised box height

    # Apply padding in normalised coords
    px1 = x1_n - padding * bw
    py1 = y1_n - padding * bh
    px2 = x2_n + padding * bw
    py2 = y2_n + padding * bh

    # Convert to pixel coords and clamp
    px1_px = max(0, int(px1 * w))
    py1_px = max(0, int(py1 * h))
    px2_px = min(w, int(px2 * w))
    py2_px = min(h, int(py2 * h))

    # Guard against degenerate crop
    if px2_px <= px1_px or py2_px <= py1_px:
        return frame.copy(), (0, 0, w, h)

    return frame[py1_px:py2_px, px1_px:px2_px].copy(), (px1_px, py1_px, px2_px, py2_px)
