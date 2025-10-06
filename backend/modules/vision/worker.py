"""
Vision Worker: Captures screen frames and stores them in a buffer.
"""

import mss
import cv2
import numpy as np
import time
import threading
from collections import deque
from typing import Optional, List, Tuple

from services.config_service import get_config_value
from services.logger_service import log_audit_entry, AuditStatus


class VisionBuffer:
    """Circular buffer for storing frames."""

    def __init__(self):
        buffer_sec = get_config_value("vision.buffer_sec", 4)
        fps = get_config_value("vision.fps", 5)
        self.max_frames = int(buffer_sec * fps)
        self.frames = deque(maxlen=self.max_frames)
        self.lock = threading.Lock()

    def push(self, frame_bgr: np.ndarray):
        """Add a frame to the buffer."""
        with self.lock:
            timestamp = time.time()
            self.frames.append((timestamp, frame_bgr.copy()))

    def get_latest_frames(self, n: int = 1) -> List[Tuple[float, np.ndarray]]:
        """Get the latest N frames."""
        with self.lock:
            if not self.frames:
                return []
            return list(self.frames)[-n:]

    def get_frames_in_time_window(
        self, seconds: float = 4.0
    ) -> List[Tuple[float, np.ndarray]]:
        """Get frames from the last N seconds."""
        with self.lock:
            if not self.frames:
                return []

            current_time = time.time()
            result = []
            for timestamp, frame in reversed(self.frames):
                if current_time - timestamp <= seconds:
                    result.append((timestamp, frame))
                else:
                    break
            return list(reversed(result))

    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.frames.clear()


class ScreenCapturer:
    """Screen capturer running in background."""

    def __init__(self, vision_buffer: VisionBuffer):
        self.buf = vision_buffer
        self.running = False
        self.capture_thread = None

    def start(self):
        """Start screen capture."""
        if not get_config_value("vision.enabled", False):
            log_audit_entry(
                "vision_disabled", "[Vision] Vision module disabled", AuditStatus.INFO
            )
            return

        if self.running:
            return

        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        log_audit_entry(
            "vision_started", "[Vision] Vision module started", AuditStatus.SUCCESS
        )

    def stop(self):
        """Stop screen capture."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join()
        log_audit_entry(
            "vision_stopped", "[Vision] Vision module stopped", AuditStatus.INFO
        )

    def _capture_loop(self):
        """Main capture loop."""
        try:
            fps = get_config_value("vision.fps", 5)
            monitor_idx_cfg = int(get_config_value("vision.monitor_index", 0) or 0)
            downscale_width = get_config_value("vision.downscale_width", 1280)
            region = get_config_value("vision.region", None)
            capture_mode = str(get_config_value("vision.capture_mode", "monitor") or "monitor").lower()
            window_title = get_config_value("vision.window_title", "") or ""
            window_process = get_config_value("vision.window_process", "") or ""

            with mss.mss() as sct:
                monitors = sct.monitors
                selected_monitor = monitors[0]
                selected_monitor_idx = 0
                selected_monitor_mss_idx = 0

                if region:
                    monitor = region
                    log_audit_entry(
                        "vision_region_selected",
                        "[Vision] Using explicit capture region",
                        AuditStatus.INFO,
                        details={"region": region},
                    )
                else:
                    physical_monitors = monitors[1:] if len(monitors) > 1 else []
                    requested_idx = monitor_idx_cfg

                    if requested_idx == -1:
                        selected_monitor = monitors[0]
                        selected_monitor_idx = -1
                        selected_monitor_mss_idx = 0
                    elif not physical_monitors:
                        selected_monitor = monitors[0]
                        selected_monitor_idx = 0
                        selected_monitor_mss_idx = 0
                    else:
                        max_idx = len(physical_monitors) - 1
                        if requested_idx < 0 or requested_idx > max_idx:
                            clamped_idx = min(max(requested_idx, 0), max_idx)
                            log_audit_entry(
                                "vision_monitor_index_adjusted",
                                "[Vision] Monitor index out of range, clamped",
                                AuditStatus.WARNING,
                                details={"requested": requested_idx, "selected": clamped_idx},
                            )
                            requested_idx = clamped_idx
                        selected_monitor_idx = requested_idx
                        selected_monitor_mss_idx = requested_idx + 1
                        selected_monitor = physical_monitors[selected_monitor_idx]

                    monitor = selected_monitor
                    log_audit_entry(
                        "vision_monitor_selected",
                        "[Vision] Monitor selected for capture",
                        AuditStatus.INFO,
                        details={
                            "capture_mode": capture_mode,
                            "index": selected_monitor_idx,
                            "mss_index": selected_monitor_mss_idx,
                            "monitor": monitor,
                        },
                    )

                last_window_hwnd = None
                window_not_found_logged = False

                while self.running:
                    try:
                        current_monitor = monitor

                        if capture_mode == "window" and not region:
                            window_info = _resolve_window_rect(window_title, window_process)
                            if window_info:
                                current_monitor = window_info["rect"]
                                if last_window_hwnd != window_info.get("hwnd"):
                                    log_audit_entry(
                                        "vision_window_selected",
                                        "[Vision] Window selected for capture",
                                        AuditStatus.INFO,
                                        details={
                                            "title": window_info.get("title"),
                                            "process": window_info.get("process"),
                                            "rect": current_monitor,
                                        },
                                    )
                                last_window_hwnd = window_info.get("hwnd")
                                window_not_found_logged = False
                            else:
                                current_monitor = selected_monitor
                                if not window_not_found_logged:
                                    log_audit_entry(
                                        "vision_window_not_found",
                                        "[Vision] Window not found, falling back to monitor capture",
                                        AuditStatus.WARNING,
                                        details={"title": window_title, "process": window_process},
                                    )
                                    window_not_found_logged = True
                                    last_window_hwnd = None
                        elif capture_mode not in ("monitor", "window") and not region:
                            current_monitor = selected_monitor
                            if not window_not_found_logged:
                                log_audit_entry(
                                    "vision_capture_mode_unknown",
                                    "[Vision] Unknown capture mode, using monitor",
                                    AuditStatus.WARNING,
                                    details={"capture_mode": capture_mode},
                                )
                                window_not_found_logged = True

                        screenshot = sct.grab(current_monitor)
                        frame = np.array(screenshot)

                        if frame.shape[2] == 4:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                        if downscale_width and frame.shape[1] > downscale_width:
                            h, w = frame.shape[:2]
                            downscale_height = int(h * (downscale_width / w))
                            frame = cv2.resize(
                                frame,
                                (downscale_width, downscale_height),
                                interpolation=cv2.INTER_AREA,
                            )

                        self.buf.push(frame)
                        time.sleep(1.0 / fps)

                    except Exception as e:
                        log_audit_entry(
                            "vision_capture_error",
                            f"[Vision] Capture error: {e}",
                            AuditStatus.ERROR,
                        )
                        time.sleep(0.1)

        except Exception as e:
            log_audit_entry(
                "vision_fatal_error", f"[Vision] Fatal error: {e}", AuditStatus.ERROR
            )


def _resolve_window_rect(window_title: str, window_process: str):
    try:
        import psutil
        import win32gui
        import win32process
    except Exception:
        return None

    title_filter = (window_title or "").strip().lower()
    process_filter = (window_process or "").strip().lower()

    if not title_filter and not process_filter:
        return None

    matches = []

    def _enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        window_title_current = (win32gui.GetWindowText(hwnd) or "").strip()
        if not window_title_current:
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = ""
        if pid:
            try:
                process_name = psutil.Process(pid).name()
            except Exception:
                process_name = ""
        if title_filter and title_filter not in window_title_current.lower():
            return
        if process_filter and process_filter not in (process_name or "").lower():
            return
        rect = win32gui.GetWindowRect(hwnd)
        if not rect:
            return
        left, top, right, bottom = rect
        width = max(0, right - left)
        height = max(0, bottom - top)
        if width <= 0 or height <= 0:
            return
        matches.append({
            "hwnd": hwnd,
            "rect": {"left": left, "top": top, "width": width, "height": height},
            "title": window_title_current,
            "process": process_name,
            "iconic": win32gui.IsIconic(hwnd),
        })

    try:
        win32gui.EnumWindows(_enum_handler, None)
    except Exception:
        return None

    if not matches:
        return None

    non_iconic = [m for m in matches if not m.get("iconic")]
    chosen = non_iconic[0] if non_iconic else matches[0]
    return chosen
