# Vision Module

Computer vision tools for screen analysis in LIM.

## Features

- **Screen Capture**: Captures screen frames in background thread.
- **Object Detection**: Uses YOLO for object detection.
- **OCR**: Extracts text from screen using Tesseract OCR.
- **Scene Analysis**: Detects scene changes using SSIM.
- **Motion Detection**: Analyzes optical flow for motion.
- **Death Screen Detection**: Detects game over/death screens.

## Requirements

- `opencv-python`
- `numpy`
- `mss`
- `pytesseract` (optional, for OCR)
- `psutil` (optional, for active window detection)
- `pywin32` (optional, for active window detection)

## Configuration

Configuration is handled via `config_service`. Keys:

- `vision.enabled` (bool)
- `vision.fps` (int)
- `vision.buffer_sec` (int)
- `vision.monitor_index` (int) - индекс физического монитора (0 = первый, 1 = второй и т.д., -1 = весь рабочий стол)
- `vision.downscale_width` (int)
- `vision.region` (dict or None)
- `vision.ocr_lang` (str)
- `vision.ocr_min_conf` (int)
- `vision.ocr_max_lines` (int)
- `vision.yolo_enabled` (bool)

## Usage

```python
from modules.vision import VisionService

vision = VisionService()
vision.start()

# Get recent context
context = vision.analyze_recent_context(4.0)
print(context["summary"])

vision.stop()


