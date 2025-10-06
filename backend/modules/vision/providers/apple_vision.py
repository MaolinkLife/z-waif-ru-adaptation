from typing import Dict, Any
from PIL import Image
import torch
import cv2
import traceback
from datetime import datetime

from services.logger_service import log_audit_entry, AuditStatus
from services.config_service import get_config_value
from constants.visual import (
    DEFAULT_VISUAL_MODEL,
    IMAGE_TOKEN_INDEX,
    DEFAULT_IMAGE_PROMPT,
)


class AppleVisionProvider:
    """
    Vision provider for apple/FastVLM models.
    Implements describe_image and vision context injection.
    """

    def __init__(self, model_id: str = None):
        self.model_id = model_id or get_config_value(
            "api.visual_model", DEFAULT_VISUAL_MODEL
        )

        if torch.cuda.is_available():
            self.device = "cuda"
            torch_dtype = torch.float16
        else:
            self.device = "cpu"
            torch_dtype = torch.float32

        try:
            log_audit_entry(
                "visual_provider_init",
                f"[AppleVisionProvider] Loading model {self.model_id} on device {self.device}",
                AuditStatus.INFO,
            )

            from transformers import AutoTokenizer, AutoModelForCausalLM

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, trust_remote_code=True
            )

            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                torch_dtype=torch_dtype,
                device_map=None,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            ).to(self.device)

            log_audit_entry(
                "visual_provider_loaded",
                f"[AppleVisionProvider] Model {self.model_id} ready on {self.device}",
                AuditStatus.SUCCESS,
            )

        except Exception as e:
            error_msg = f"[AppleVisionProvider] Failed to load model: {e}"
            log_audit_entry("visual_provider_error", error_msg, AuditStatus.ERROR)
            print(
                f"[ERROR] [{datetime.utcnow().isoformat()}Z] {error_msg}\n{traceback.format_exc()}"
            )
            self.model = None
            self.tokenizer = None

    def is_ready(self) -> bool:
        ready = self.model is not None and self.tokenizer is not None
        log_audit_entry(
            "visual_provider_ready_check",
            f"[AppleVisionProvider] Ready: {ready}",
            AuditStatus.INFO,
        )
        return ready

    def describe_image(
        self, image: Image.Image, prompt: str = DEFAULT_IMAGE_PROMPT
    ) -> Dict[str, Any]:
        """
        Run visual inference on input image with optional prompt.

        Args:
            image: PIL image object
            prompt: User-defined or default prompt

        Returns:
            Dict with summary, model info and status
        """
        log_audit_entry(
            "visual_provider_inference_start",
            "[AppleVisionProvider] Starting image description.",
            AuditStatus.INFO,
            details={"prompt": prompt},
        )

        if not self.is_ready():
            result = {
                "summary": "Visual module not available",
                "model": self.model_id,
                "status": "not_ready",
            }
            log_audit_entry(
                "visual_provider_inference_skipped",
                "[AppleVisionProvider] Module not ready.",
                AuditStatus.WARNING,
                details=result,
            )
            return result

        try:
            # 1. Construct input message
            messages = [{"role": "user", "content": f"<image>\n{prompt}"}]
            rendered = self.tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
            pre, post = rendered.split("<image>", 1)

            # 2. Tokenize pre/post text
            pre_ids = self.tokenizer(
                pre, return_tensors="pt", add_special_tokens=False
            ).input_ids
            post_ids = self.tokenizer(
                post, return_tensors="pt", add_special_tokens=False
            ).input_ids

            # 3. Insert special token for image
            img_tok = torch.tensor([[IMAGE_TOKEN_INDEX]], dtype=pre_ids.dtype)
            input_ids = torch.cat([pre_ids, img_tok, post_ids], dim=1).to(self.device)
            attention_mask = torch.ones_like(input_ids, device=self.device)

            # 4. Process image via vision tower
            px = (
                self.model.get_vision_tower()
                .image_processor(images=image, return_tensors="pt")["pixel_values"]
                .to(self.device, dtype=self.model.dtype)
            )

            # 5. Generate description
            with torch.no_grad():
                out = self.model.generate(
                    inputs=input_ids,
                    attention_mask=attention_mask,
                    images=px,
                    max_new_tokens=128,
                )

            text = self.tokenizer.decode(out[0], skip_special_tokens=True).strip()
            result = {
                "summary": text,
                "model": self.model_id,
                "prompt": prompt,
                "status": "success",
            }

            log_audit_entry(
                "visual_provider_inference_success",
                "[AppleVisionProvider] Image description generated successfully.",
                AuditStatus.SUCCESS,
                details={"summary_preview": text[:100]},
            )

            return result

        except Exception as e:
            error_msg = f"[AppleVisionProvider] Inference error: {e}"
            log_audit_entry(
                "visual_provider_inference_error",
                error_msg,
                AuditStatus.ERROR,
                details={"error": str(e), "traceback": traceback.format_exc()[:500]},
            )
            print(
                f"[ERROR] [{datetime.utcnow().isoformat()}Z] {error_msg}\n{traceback.format_exc()}"
            )
            return {
                "summary": f"Inference error: {e}",
                "model": self.model_id,
                "status": "error",
            }
