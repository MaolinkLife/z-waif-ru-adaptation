# services/monitor_service.py
import mss
import cv2
import numpy as np
import base64
from typing import List, Dict, Any
from io import BytesIO


def get_monitor_screens() -> List[Dict[str, Any]]:
    """Return available monitors along with preview thumbnails."""
    try:
        monitors_info = []

        with mss.mss() as sct:
            # Skip the first entry (combined display); the rest are individual monitors
            monitors = sct.monitors[1:]

            for i, monitor in enumerate(monitors):
                try:
                    # Capture a screenshot of the monitor
                    screenshot = sct.grab(monitor)
                    frame = np.array(screenshot)

                    # Convert BGRA to BGR
                    if frame.shape[2] == 4:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    # Downscale for preview (max width 300px)
                    max_preview_width = 300
                    if frame.shape[1] > max_preview_width:
                        h, w = frame.shape[:2]
                        preview_height = int(h * (max_preview_width / w))
                        preview_frame = cv2.resize(
                            frame,
                            (max_preview_width, preview_height),
                            interpolation=cv2.INTER_AREA,
                        )
                    else:
                        preview_frame = frame

                    # Convert to JPEG and encode as base64
                    _, buffer = cv2.imencode(
                        ".jpg", preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
                    )
                    preview_base64 = base64.b64encode(buffer).decode("utf-8")

                    monitors_info.append(
                        {
                            "index": i,
                            "width": monitor["width"],
                            "height": monitor["height"],
                            "left": monitor["left"],
                            "top": monitor["top"],
                            "preview": preview_base64,
                        }
                    )

                except Exception as e:
                    # If preview generation fails, add the monitor without it
                    monitors_info.append(
                        {
                            "index": i,
                            "width": monitor["width"],
                            "height": monitor["height"],
                            "left": monitor["left"],
                            "top": monitor["top"],
                            "preview": None,
                        }
                    )

        return monitors_info

    except Exception as e:
        print(f"[Monitor Service] Error getting monitors: {e}")
        return []


def get_monitor_info() -> Dict[str, Any]:
    """Return basic information about the monitors."""
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            return {
                "total_monitors": max(
                    0, len(monitors) - 1
                ),  # subtract 1 because the first element is the combined screen
                "monitors": [
                    {
                        "index": i,
                        "width": monitor["width"],
                        "height": monitor["height"],
                        "left": monitor["left"],
                        "top": monitor["top"],
                    }
                    for i, monitor in enumerate(monitors[1:])
                ],
            }
    except Exception as e:
        return {"total_monitors": 0, "monitors": [], "error": str(e)}
