"""
Vision Analyzer: Analyzes visual signals from captured frames.
Includes YOLO object detection, OCR text extraction, SSIM comparison, and optical flow.
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Any, Optional

# Optional OCR
try:
    import pytesseract

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("[Vision] OCR not available. Install pytesseract for OCR support.")


class VisionAnalyzer:
    """Analyzes visual signals (tools)."""

    def __init__(self):
        self.keywords = {
            "en": [
                "you died",
                "wasted",
                "defeat",
                "game over",
                "mission failed",
                "retry",
                "respawn",
                "continue?",
                "try again",
            ],
            "ru": [
                "вы погибли",
                "поражение",
                "неудача",
                "конец игры",
                "повторить",
                "возрождение",
                "продолжить",
                "попробуйте снова",
            ],
        }

        # YOLO detector
        from services.yolo_detector import YOLODetector

        self.yolo_detector = YOLODetector(
            model_path="storage/models/yolov8n.pt",
            conf_threshold=0.5,
        )

    # === YOLO ===
    def detect_objects_yolo(self, frame: np.ndarray) -> List[Dict]:
        """Detect objects in a frame using YOLO."""
        return self.yolo_detector.detect(frame)

    def summarize_yolo_detections(self, detections: List[Dict]) -> str:
        """Generate a text summary of YOLO detections."""
        if not detections:
            return "Nothing detected."

        object_counts = {}
        for det in detections:
            obj_class = det["class"]
            object_counts[obj_class] = object_counts.get(obj_class, 0) + 1

        summary_parts = []
        for obj, count in object_counts.items():
            summary_parts.append(f"{count} {obj}" if count > 1 else f"one {obj}")

        return f"I see: {', '.join(summary_parts)}."

    # === OCR ===
    def extract_text_with_ocr(self, frame: np.ndarray) -> Tuple[str, float]:
        """Extract text from image using OCR."""
        if not OCR_AVAILABLE:
            return "", 0.0

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            h, w = thresh.shape
            if w < 600 or h < 400:
                scale_factor = min(600 / w, 400 / h)
                new_w, new_h = int(w * scale_factor), int(h * scale_factor)
                thresh = cv2.resize(
                    thresh, (new_w, new_h), interpolation=cv2.INTER_CUBIC
                )

            text = pytesseract.image_to_string(thresh, lang="eng+rus")
            return text.strip(), 0.8
        except Exception as e:
            print(f"[Vision] OCR error: {e}")
            return "", 0.0

    # === SSIM ===
    def calculate_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calculate SSIM between two images."""
        try:
            gray1 = (
                cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if len(img1.shape) == 3 else img1
            )
            gray2 = (
                cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if len(img2.shape) == 3 else img2
            )
            return self._simple_ssim(gray1, gray2)
        except Exception:
            return 1.0

    def _simple_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Simplified SSIM calculation."""
        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)

        mu1, mu2 = np.mean(img1), np.mean(img2)
        sigma1_sq, sigma2_sq = np.var(img1), np.var(img2)
        sigma12 = np.cov(img1.flatten(), img2.flatten())[0, 1]

        C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2

        return ((2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)) / (
            (mu1**2 + mu2**2 + C1) * (sigma1_sq + sigma2_sq + C2)
        )

    # === Optical Flow ===
    def calculate_optical_flow(
        self, prev_frame: np.ndarray, curr_frame: np.ndarray
    ) -> Dict[str, Any]:
        """Calculate optical flow between two frames."""
        try:
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )

            mean_flow = np.mean(flow, axis=(0, 1))
            dx, dy = mean_flow[0], mean_flow[1]
            magnitude = np.sqrt(dx**2 + dy**2)

            direction = (
                "down"
                if abs(dy) > abs(dx) and dy > 0
                else (
                    "up"
                    if abs(dy) > abs(dx) and dy < 0
                    else "right" if dx > 0 else "left"
                )
            )

            return {
                "direction": direction,
                "magnitude": float(magnitude),
                "flow_x": float(dx),
                "flow_y": float(dy),
            }
        except Exception as e:
            print(f"[Vision] Optical flow error: {e}")
            return {"direction": "unknown", "magnitude": 0.0}

    # === Death screen ===
    def detect_death_screen(self, text: str, language: str = "ru-RU") -> Optional[str]:
        """Detect death screen by keywords."""
        text_lower = text.lower()
        keywords = (
            self.keywords["ru"] if language.startswith("ru") else self.keywords["en"]
        )

        for keyword in keywords:
            if keyword.lower() in text_lower:
                return keyword
        return None
