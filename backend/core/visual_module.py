import base64
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from PIL import Image, UnidentifiedImageError

from constants.visual import DEFAULT_VISUAL_MODEL
from modules.vision.providers.apple_vision import AppleVisionProvider
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry


class VisualModule:
    """Wrapper around the configured visual provider."""

    def __init__(self, provider_name: Optional[str] = None):
        self.provider_name = provider_name or get_config_value(
            "vision.active_provider", "apple_vision"
        )
        self.provider = self._load_provider()

    def _load_provider(self):
        if self.provider_name == "apple_vision":
            return AppleVisionProvider()
        raise ValueError(f"Unknown vision provider: {self.provider_name}")

    def is_ready(self) -> bool:
        return bool(self.provider and self.provider.is_ready())

    def describe_image(
        self,
        image: Image.Image,
        prompt: str = "Describe the image in detail in English.",
    ) -> Dict[str, Any]:
        return self.provider.describe_image(image, prompt)

    # ------------------------------------------------------------------
    # Attachment processing
    # ------------------------------------------------------------------
    def describe_media_attachments(
        self, media_payload: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not media_payload:
            return {}
        if not get_config_value("vision.enabled", False):
            log_audit_entry(
                "visual_module_disabled",
                "[VisualModule] Attachment analysis skipped: vision disabled.",
                AuditStatus.INFO,
            )
            return {}
        if not self.is_ready():
            log_audit_entry(
                "visual_module_not_ready",
                "[VisualModule] Attachment analysis skipped: provider not ready.",
                AuditStatus.WARNING,
            )
            return {}

        prompt = get_config_value(
            "vision.attachment_prompt",
            "Describe the user-provided image in detail in English.",
        )

        items: List[Dict[str, Any]] = []
        updates: List[Dict[str, Any]] = []

        for index, media in enumerate(media_payload):
            category = (media.get("category") or "").lower()
            if category != "image":
                continue

            data = media.get("data")
            if not data:
                continue

            try:
                image = self._decode_base64_image(data)
                try:
                    result = self.describe_image(image, prompt)
                finally:
                    image.close()
            except UnidentifiedImageError as exc:
                log_audit_entry(
                    "visual_module_image_error",
                    "[VisualModule] Failed to decode image attachment.",
                    AuditStatus.ERROR,
                    details={"index": index, "error": str(exc)},
                )
                continue
            except Exception as exc:
                log_audit_entry(
                    "visual_module_attachment_error",
                    "[VisualModule] Error while describing attachment.",
                    AuditStatus.ERROR,
                    details={"index": index, "error": str(exc)},
                )
                continue

            summary = (result.get("summary") or "").strip()
            if not summary:
                continue

            item_data = {
                "index": index,
                "description": summary,
                "model": result.get("model", DEFAULT_VISUAL_MODEL),
                "status": result.get("status", "success"),
            }
            items.append(item_data)
            updates.append({"index": index, "description": summary})

            log_audit_entry(
                "visual_module_attachment_described",
                "[VisualModule] Attachment described successfully.",
                AuditStatus.SUCCESS,
                details={"index": index, "summary_preview": summary[:120]},
            )

        if not items:
            return {}

        return {"items": items, "updates": updates, "prompt": prompt}

    # ------------------------------------------------------------------
    # Screen capture processing
    # ------------------------------------------------------------------
    def describe_screen_snapshot(self) -> Optional[Dict[str, Any]]:
        if not get_config_value("vision.enabled", False):
            log_audit_entry(
                "visual_module_disabled_screen",
                "[VisualModule] Screen analysis skipped: vision disabled.",
                AuditStatus.INFO,
            )
            return None

        try:
            from modules.vision.service import VisionService
        except Exception as exc:
            log_audit_entry(
                "visual_module_service_import_error",
                "[VisualModule] Failed to import VisionService for screen analysis.",
                AuditStatus.ERROR,
                details={"error": str(exc)},
            )
            return None

        vision_service = VisionService()
        latest_frames = vision_service.buffer.get_latest_frames(1)

        if not latest_frames:
            log_audit_entry(
                "visual_module_no_frames",
                "[VisualModule] No screen frames available for vision analysis.",
                AuditStatus.INFO,
            )
            baseline = vision_service.analyze_recent_context(4.0)
            if baseline and baseline.get("summary"):
                return {
                    "description": baseline["summary"],
                    "captured_at": baseline.get("timestamp"),
                    "source": "vision_service",
                    "confidence": baseline.get("confidence", 0.0),
                }
            return None

        captured_at, frame_bgr = latest_frames[-1]
        if not self.is_ready():
            log_audit_entry(
                "visual_module_not_ready_screen",
                "[VisualModule] Screen analysis skipped: provider not ready.",
                AuditStatus.WARNING,
            )
            return None

        prompt = get_config_value(
            "vision.screen_prompt",
            "Describe the current user screen in detail in English.",
        )

        try:
            rgb_frame = frame_bgr[:, :, ::-1]
            image = Image.fromarray(rgb_frame).convert("RGB")
            result = self.describe_image(image, prompt)
        except Exception as exc:
            log_audit_entry(
                "visual_module_screen_error",
                "[VisualModule] Error while describing screen snapshot.",
                AuditStatus.ERROR,
                details={"error": str(exc)},
            )
            return None

        summary = (result.get("summary") or "").strip()
        if not summary:
            return None

        log_audit_entry(
            "visual_module_screen_described",
            "[VisualModule] Screen snapshot described successfully.",
            AuditStatus.SUCCESS,
            details={"summary_preview": summary[:120]},
        )

        return {
            "description": summary,
            "captured_at": datetime.utcfromtimestamp(captured_at).isoformat() + "Z",
            "model": result.get("model", DEFAULT_VISUAL_MODEL),
            "prompt": prompt,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _decode_base64_image(data: str) -> Image.Image:
        raw = base64.b64decode(data, validate=False)
        with Image.open(BytesIO(raw)) as image:
            return image.convert("RGB")
