"""
Vision Service: Main service for vision analysis.
"""

import os
import threading
import time
from typing import Optional, Dict, Any
from datetime import datetime

from .worker import VisionBuffer, ScreenCapturer
from .analyzer import VisionAnalyzer
from services.config_service import get_config_value
from services.logger_service import log_audit_entry, AuditStatus


class VisionService:
    """Main vision service for LIM."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(VisionService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return

        self.buffer = VisionBuffer()
        self.capturer = ScreenCapturer(self.buffer)
        self.analyzer = VisionAnalyzer()
        self.initialized = True

    def start(self):
        """Start the vision service."""
        self.capturer.start()

    def stop(self):
        """Stop the vision service."""
        self.capturer.stop()

    def analyze_recent_context(self, seconds: float = 4.0) -> Dict[str, Any]:
        """
        Deterministic screen analysis:
        - Active window (title + process)
        - Top OCR lines with high confidence
        - Raw YOLO detections (evidence only)
        - SSIM/Optical Flow as auxiliary evidence
        """
        frames = self.buffer.get_frames_in_time_window(seconds)
        if not frames:
            log_audit_entry(
                "vision_no_frames",
                f"[Vision] No frames in {seconds}s",
                AuditStatus.INFO,
            )
            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event": "no_data",
                "summary": "No visual data available",
                "confidence": 0.0,
            }

        _, last_frame = frames[-1]
        prev_frame = frames[-2][1] if len(frames) >= 2 else None

        _maybe_save_debug_frame(last_frame)

        capture_bounds = _get_capture_bounds()
        win = _get_active_window_info_safe()
        window_on_capture = True
        if win:
            win = dict(win)
            window_rect = win.get("rect")
            if capture_bounds and window_rect:
                overlap_ratio = _rect_overlap_ratio(window_rect, capture_bounds)
                window_on_capture = overlap_ratio >= 0.1
                win["overlap_ratio"] = round(overlap_ratio, 3)
            elif capture_bounds and not window_rect:
                window_on_capture = False
            else:
                window_on_capture = True
            win["matches_capture"] = window_on_capture
            if not window_on_capture:
                log_audit_entry(
                    "vision_window_outside_capture",
                    "[Vision] Active window outside captured region",
                    AuditStatus.INFO,
                    details={"window": win, "capture": capture_bounds},
                )

        ocr_lang = get_config_value("vision.ocr_lang", "rus+eng")
        min_conf = int(get_config_value("vision.ocr_min_conf", 70))
        max_lines = int(get_config_value("vision.ocr_max_lines", 5))
        text_blocks = _extract_top_text_blocks(
            last_frame, lang=ocr_lang, min_conf=min_conf, max_lines=max_lines
        )

        yolo_list = []
        yolo_summary = None
        if get_config_value("vision.yolo_enabled", True):
            try:
                yolo_list = self.analyzer.detect_objects_yolo(last_frame) or []
                yolo_summary = self.analyzer.summarize_yolo_detections(yolo_list)
                log_audit_entry(
                    "vision_yolo_detected" if yolo_list else "vision_yolo_empty",
                    f"[Vision] YOLO: {len(yolo_list)} detections",
                    AuditStatus.INFO,
                    details={"detections": yolo_list[:10]},
                )
            except Exception as e:
                log_audit_entry(
                    "vision_yolo_error", f"[Vision] YOLO error: {e}", AuditStatus.ERROR
                )

        scene_change = None
        flow_info = None
        if prev_frame is not None:
            try:
                ssim_value = self.analyzer.calculate_ssim(prev_frame, last_frame)
                scene_change = {
                    "ssim": float(ssim_value),
                    "ssim_drop": float(1.0 - ssim_value),
                }
                log_audit_entry(
                    "vision_scene_change",
                    f"[Vision] SSIM={ssim_value:.6f}, drop={1.0 - ssim_value:.6f}",
                    AuditStatus.INFO,
                    details=scene_change,
                )
            except Exception as e:
                log_audit_entry(
                    "vision_ssim_error", f"[Vision] SSIM error: {e}", AuditStatus.ERROR
                )

            try:
                flow_info = self.analyzer.calculate_optical_flow(prev_frame, last_frame)
            except Exception as e:
                log_audit_entry(
                    "vision_optical_flow_error",
                    f"[Vision] Flow error: {e}",
                    AuditStatus.ERROR,
                )

        top_lines = [b["text"] for b in text_blocks if b.get("text")]
        readable = " | ".join(top_lines) if top_lines else "No text recognized"

        parts = []
        if win and win.get("matches_capture", True):
            title = win.get("title", "")
            process_name = win.get("process", "")
            parts.append(f"Active window: \"{title}\" (proc: {process_name})")
        parts.append(f"Screen text: {readable}")
        if yolo_summary and yolo_summary != "Nothing detected.":
            parts.append(f"Detected: {yolo_summary}")

        summary = ". ".join(parts) + "."

        ocr_conf = 0.0
        if text_blocks:
            confs = [
                b["conf"]
                for b in text_blocks
                if isinstance(b.get("conf"), (int, float))
            ]
            if confs:
                confs_sorted = sorted(confs)
                ocr_conf = confs_sorted[len(confs_sorted) // 2] / 100.0

        yolo_conf = max((d.get("confidence", 0.0) for d in yolo_list), default=0.0)
        confidence = round(min(0.95, max(0.55, ocr_conf, yolo_conf)), 2)

        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "monitor": get_config_value("vision.monitor_index", 1),
            "event": "screen_snapshot",
            "cause": "none",
            "confidence": confidence,
            "summary": summary,
            "evidence": {
                "window": win or {},
                "capture": capture_bounds or {},
                "ocr": {
                    "lines": text_blocks,
                    "lang": ocr_lang,
                    "min_conf": min_conf,
                },
                "yolo": {
                    "detections": yolo_list,
                    "summary": yolo_summary,
                },
                "scene_change": scene_change or {},
                "optical_flow": flow_info or {},
            },
        }

        log_audit_entry(
            "vision_analysis_complete",
            f"[Vision] OK: conf={confidence:.2f}",
            AuditStatus.INFO,
            details=result,
        )
        return result

    def handle_vision_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Handle vision context query."""
        vision_keywords = [
            "видела",
            "заметила",
            "на экране",
            "ты видишь",
            "что там",
            "what's on screen",
            "do you see",
            "what do you see",
        ]

        query_lower = query.lower()
        if any(keyword in query_lower for keyword in vision_keywords):
            return self.analyze_recent_context(4.0)

        return None


_debug_save_lock = threading.Lock()
_debug_last_saved = 0.0


def _maybe_save_debug_frame(frame):
    if not get_config_value("vision.debug_save", False):
        return

    path_cfg = get_config_value("vision.debug_path", None)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temp", "vision"))
    save_dir = os.path.abspath(path_cfg) if path_cfg else base_dir

    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.join(save_dir, f"vision_{timestamp}.png")
        import cv2
        if not cv2.imwrite(filename, frame):
            raise RuntimeError("cv2.imwrite returned False")

        latest_path = os.path.join(save_dir, "last_frame.png")
        if latest_path != filename:
            try:
                cv2.imwrite(latest_path, frame)
            except Exception:
                pass

        now = time.time()
        global _debug_last_saved
        with _debug_save_lock:
            if now - _debug_last_saved > 5:
                log_audit_entry(
                    "vision_debug_frame_saved",
                    "[Vision] Debug frame saved",
                    AuditStatus.INFO,
                    details={"path": filename},
                )
                _debug_last_saved = now

    except Exception as e:
        log_audit_entry(
            "vision_debug_save_error",
            f"[Vision] Failed to save debug frame: {e}",
            AuditStatus.ERROR,
        )



# --- Helpers ---
def _get_active_window_info_safe():
    try:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid).name() if pid else ""
        rect = None
        try:
            raw_rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            raw_rect = None
        if raw_rect and len(raw_rect) == 4:
            left, top, right, bottom = raw_rect
            width = max(0, int(right) - int(left))
            height = max(0, int(bottom) - int(top))
            if width > 0 and height > 0:
                rect = {
                    "left": int(left),
                    "top": int(top),
                    "width": width,
                    "height": height,
                }
        title = title.strip()
        proc = (proc or "").strip()
        if not title and not proc:
            return None
        info = {"title": title[:128], "process": proc[:64]}
        if rect:
            info["rect"] = rect
        return info
    except Exception:
        return None




def _get_capture_bounds():
    region_cfg = get_config_value("vision.region", None)
    rect = _normalize_rect_dict(region_cfg) if region_cfg else None
    if rect:
        return rect

    capture_mode = str(get_config_value("vision.capture_mode", "monitor") or "monitor").lower()
    if capture_mode != "monitor":
        return None

    try:
        monitor_idx_cfg = int(get_config_value("vision.monitor_index", 0) or 0)
    except Exception:
        monitor_idx_cfg = 0

    try:
        import mss

        with mss.mss() as sct:
            monitors = sct.monitors
            if not monitors:
                return None

            if monitor_idx_cfg == -1 or len(monitors) == 1:
                return _normalize_rect_dict(monitors[0])

            physical_monitors = monitors[1:] if len(monitors) > 1 else []
            if not physical_monitors:
                return _normalize_rect_dict(monitors[0])

            max_idx = len(physical_monitors) - 1
            if monitor_idx_cfg < 0 or monitor_idx_cfg > max_idx:
                monitor_idx_cfg = min(max(monitor_idx_cfg, 0), max_idx)

            return _normalize_rect_dict(physical_monitors[monitor_idx_cfg])
    except Exception:
        return None


def _normalize_rect_dict(data):
    if not isinstance(data, dict):
        return None

    def _to_int(value):
        try:
            return int(value)
        except Exception:
            return None

    left = _to_int(data.get("left", data.get("x")))
    top = _to_int(data.get("top", data.get("y")))
    if left is None or top is None:
        return None

    width_value = data.get("width")
    if width_value is None and data.get("right") is not None:
        right = _to_int(data.get("right"))
        if right is None:
            return None
        width = right - left
    else:
        width = _to_int(width_value) if width_value is not None else None

    height_value = data.get("height")
    if height_value is None and data.get("bottom") is not None:
        bottom = _to_int(data.get("bottom"))
        if bottom is None:
            return None
        height = bottom - top
    else:
        height = _to_int(height_value) if height_value is not None else None

    if width is None or height is None:
        return None

    if width <= 0 or height <= 0:
        return None

    return {"left": left, "top": top, "width": width, "height": height}


def _rects_intersect(rect_a, rect_b):
    try:
        ax1 = int(rect_a.get("left"))
        ay1 = int(rect_a.get("top"))
        ax2 = ax1 + int(rect_a.get("width"))
        ay2 = ay1 + int(rect_a.get("height"))
        bx1 = int(rect_b.get("left"))
        by1 = int(rect_b.get("top"))
        bx2 = bx1 + int(rect_b.get("width"))
        by2 = by1 + int(rect_b.get("height"))
    except Exception:
        return False

    if ax1 >= ax2 or ay1 >= ay2 or bx1 >= bx2 or by1 >= by2:
        return False

    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def _rect_overlap_ratio(rect_a, rect_b):
    try:
        ax1 = int(rect_a.get("left"))
        ay1 = int(rect_a.get("top"))
        aw = int(rect_a.get("width"))
        ah = int(rect_a.get("height"))
        bx1 = int(rect_b.get("left"))
        by1 = int(rect_b.get("top"))
        bw = int(rect_b.get("width"))
        bh = int(rect_b.get("height"))
    except Exception:
        return 0.0

    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0

    ax2 = ax1 + aw
    ay2 = ay1 + ah
    bx2 = bx1 + bw
    by2 = by1 + bh

    inter_left = max(ax1, bx1)
    inter_top = max(ay1, by1)
    inter_right = min(ax2, bx2)
    inter_bottom = min(ay2, by2)

    if inter_left >= inter_right or inter_top >= inter_bottom:
        return 0.0

    intersection_area = (inter_right - inter_left) * (inter_bottom - inter_top)
    window_area = aw * ah
    if window_area <= 0:
        return 0.0

    return intersection_area / float(window_area)


def _extract_top_text_blocks(frame, lang="rus+eng", min_conf=70, max_lines=5):
    try:
        import cv2
        import pytesseract
        from pytesseract import Output

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.4, beta=0)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        data = pytesseract.image_to_data(th, lang=lang, output_type=Output.DICT)
        n = len(data["text"])
        rows = []
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1.0
            if conf < float(min_conf):
                continue
            x, y, w, h = (
                int(data["left"][i]),
                int(data["top"][i]),
                int(data["width"][i]),
                int(data["height"][i]),
            )
            rows.append(
                {"text": text, "conf": conf, "bbox": {"x": x, "y": y, "w": w, "h": h}}
            )

        rows.sort(key=lambda r: r["conf"], reverse=True)
        return rows[:max_lines]
    except Exception:
        return []
