# services/yolo_detector.py
import numpy as np
from typing import List, Dict
from ultralytics import YOLO
import torch


class YOLODetector:
    def __init__(self, model_path: str = "yolov8m.pt", conf_threshold: float = 0.5):
        """
        Initialize the YOLO detector.
        :param model_path: Path to model weights (e.g., yolov8n.pt)
        :param conf_threshold: Confidence threshold for detections
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.model = None
        self.class_names = {}
        self._load_model()

    def _load_model(self):
        """Load the YOLO model."""
        try:
            self.model = YOLO(self.model_path)
            # Select device
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            # Read class names
            self.class_names = self.model.names
            print(f"[YOLO] Model loaded. Device: {self.device}")
        except Exception as e:
            print(f"[YOLO] Failed to load model: {e}")
            raise

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect objects on a single frame.
        :param frame: Image in numpy ndarray (BGR) format
        :return: List of detections with class, confidence, and bounding box
        """
        try:
            # Run inference
            results = self.model(frame, verbose=False, conf=self.conf_threshold)
            detections = []

            # Process results
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        # Extract data
                        cls_id = int(boxes.cls[i].item())
                        conf = float(boxes.conf[i].item())
                        xyxy = boxes.xyxy[i].cpu().numpy().tolist()

                        # Map to class name
                        class_name = self.class_names.get(cls_id, f"unknown_{cls_id}")

                        detections.append(
                            {
                                "class": class_name,
                                "confidence": conf,
                                "bbox": xyxy,  # [x1, y1, x2, y2]
                            }
                        )
            return detections
        except Exception as e:
            print(f"[YOLO] Detection error: {e}")
            return []
