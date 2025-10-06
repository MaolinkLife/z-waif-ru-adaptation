from __future__ import annotations

import time
from typing import Dict

import requests

from modules.tts.providers.base import TTSProvider, TTSProviderError
from modules.tts.types import TTSRequest, TTSResult
from services.logger_service import AuditStatus, log_audit_entry


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"

    def __init__(self, config: Dict[str, any]) -> None:
        self._config = config or {}
        print("[ElevenLabsProvider] Инициализация провайдера ElevenLabs.")
        log_audit_entry(
            "elevenlabs_provider_init",
            "[ElevenLabsProvider/Init] Провайдер ElevenLabs инициализирован.",
            AuditStatus.INFO,
            details={
                "has_api_key": bool(self._config.get("api_key")),
                "has_voice_id": bool(self._config.get("voice_id")),
                "model_id": self._config.get("model_id"),
                "stability": self._config.get("stability"),
                "similarity": self._config.get("similarity"),
            },
        )

    def is_available(self) -> bool:
        available = bool(self._config.get("api_key") and self._config.get("voice_id"))
        print(f"[ElevenLabsProvider] Проверка доступности провайдера: {available}.")
        log_audit_entry(
            "elevenlabs_availability_check",
            "[ElevenLabsProvider/Availability] Проверка доступности провайдера.",
            AuditStatus.INFO if available else AuditStatus.WARNING,
            details={
                "has_api_key": bool(self._config.get("api_key")),
                "has_voice_id": bool(self._config.get("voice_id")),
            },
        )
        return available

    def synthesize(self, request: TTSRequest, output_path: str) -> TTSResult:
        api_key = self._config.get("api_key")
        voice_id = self._config.get("voice_id")
        model_id = self._config.get("model_id", "eleven_multilingual_v2")
        stability = self._config.get("stability", 0.5)
        similarity = self._config.get("similarity", 0.75)

        print("[ElevenLabsProvider] Начало синтеза текста в речь.")
        log_audit_entry(
            "elevenlabs_synthesis_start",
            "[ElevenLabsProvider/Synthesis] Начало синтеза текста в речь.",
            AuditStatus.INFO,
            details={
                "text_length": len(request.text),
                "voice_id": voice_id,
                "model_id": model_id,
                "stability": stability,
                "similarity": similarity,
                "output_path": output_path,
            },
        )

        if not api_key or not voice_id:
            print("[ElevenLabsProvider] Ошибка: Отсутствует API-ключ или ID голоса.")
            log_audit_entry(
                "elevenlabs_config_error",
                "[ElevenLabsProvider/Config] Отсутствует API-ключ или ID голоса.",
                AuditStatus.ERROR,
                details={"has_api_key": bool(api_key), "has_voice_id": bool(voice_id)},
            )
            raise TTSProviderError("Missing ElevenLabs API Key or Voice ID.")

        headers = {"xi-api-key": api_key, "Content-Type": "application/json"}

        # Логируем payload перед отправкой (без чувствительных данных)
        payload = {
            "text": request.text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
            },
        }

        print("[ElevenLabsProvider] Подготовка запроса к API ElevenLabs.")
        log_audit_entry(
            "elevenlabs_request_prepared",
            "[ElevenLabsProvider/Request] Запрос подготовлен для отправки.",
            AuditStatus.INFO,
            details={
                "text_preview": (
                    request.text[:100] + "..."
                    if len(request.text) > 100
                    else request.text
                ),
                "text_length": len(request.text),
                "voice_id": voice_id,
                "model_id": model_id,
                "request_headers": headers,
            },
        )

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        start = time.time()
        try:
            print("[ElevenLabsProvider] Отправка запроса к API ElevenLabs.")
            log_audit_entry(
                "elevenlabs_request_sent",
                "[ElevenLabsProvider/API] Запрос отправлен на API.",
                AuditStatus.INFO,
                details={"url": url, "method": "POST", "timeout": 60},
            )

            response = requests.post(
                url, headers=headers, json=payload, stream=True, timeout=60
            )

            print(f"[ElevenLabsProvider] Получен ответ от API: {response.status_code}")
            log_audit_entry(
                "elevenlabs_response_received",
                "[ElevenLabsProvider/API] Ответ получен от API.",
                AuditStatus.INFO,
                details={
                    "status_code": response.status_code,
                    "content_length": response.headers.get("content-length"),
                    "content_type": response.headers.get("content-type"),
                    "response_headers": dict(response.headers),
                },
            )

            if response.status_code == 200:
                print("[ElevenLabsProvider] Начало загрузки аудиофайла.")
                log_audit_entry(
                    "elevenlabs_downloading_audio",
                    "[ElevenLabsProvider/Download] Начало загрузки аудиофайла.",
                    AuditStatus.INFO,
                    details={
                        "output_path": output_path,
                        "content_length": response.headers.get("content-length"),
                    },
                )

                with open(output_path, "wb") as fh:
                    chunk_count = 0
                    total_bytes = 0
                    for chunk in response.iter_content(chunk_size=4096):
                        if chunk:
                            fh.write(chunk)
                            chunk_count += 1
                            total_bytes += len(chunk)

                            # Логируем прогресс каждые 10 чанков
                            if chunk_count % 10 == 0:
                                print(
                                    f"[ElevenLabsProvider] Прогресс загрузки: {chunk_count} чанков."
                                )
                                log_audit_entry(
                                    "elevenlabs_download_progress",
                                    "[ElevenLabsProvider/Download] Прогресс загрузки.",
                                    AuditStatus.INFO,
                                    details={
                                        "chunk_number": chunk_count,
                                        "bytes_downloaded": total_bytes,
                                        "chunk_size": len(chunk),
                                    },
                                )

                print("[ElevenLabsProvider] Загрузка аудиофайла завершена.")
                log_audit_entry(
                    "elevenlabs_download_completed",
                    "[ElevenLabsProvider/Download] Загрузка аудиофайла завершена.",
                    AuditStatus.INFO,
                    details={
                        "output_path": output_path,
                        "total_bytes": total_bytes,
                        "chunks_count": chunk_count,
                    },
                )
            else:
                error_details = {
                    "status_code": response.status_code,
                    "response_text_preview": (
                        response.text[:500] + "..."
                        if len(response.text) > 500
                        else response.text
                    ),
                    "response_headers": dict(response.headers),
                }

                print(f"[ElevenLabsProvider] Ошибка API: {response.status_code}")
                log_audit_entry(
                    "elevenlabs_api_error",
                    f"[ElevenLabsProvider/API] API вернул ошибку {response.status_code}.",
                    AuditStatus.ERROR,
                    details=error_details,
                )

                raise TTSProviderError(
                    f"ElevenLabs API error {response.status_code}: {response.text}"
                )
        except requests.exceptions.Timeout:
            print("[ElevenLabsProvider] Таймаут при отправке запроса.")
            log_audit_entry(
                "elevenlabs_request_timeout",
                "[ElevenLabsProvider/API] Запрос истек по времени.",
                AuditStatus.ERROR,
                details={"timeout_value": 60, "url": url},
            )
            raise TTSProviderError("ElevenLabs request timed out after 60 seconds")
        except requests.exceptions.ConnectionError as e:
            print(f"[ElevenLabsProvider] Ошибка подключения: {e}")
            log_audit_entry(
                "elevenlabs_connection_error",
                "[ElevenLabsProvider/API] Произошла ошибка подключения.",
                AuditStatus.ERROR,
                details={"error": str(e), "url": url},
            )
            raise TTSProviderError(f"ElevenLabs connection error: {e}")
        except Exception as exc:
            print(f"[ElevenLabsProvider] Синтез завершился с ошибкой: {exc}")
            log_audit_entry(
                "elevenlabs_synthesis_failed",
                "[ElevenLabsProvider/Synthesis] Синтез завершился с ошибкой.",
                AuditStatus.ERROR,
                details={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "url": url,
                },
            )
            raise TTSProviderError(f"ElevenLabs synthesis failed: {exc}") from exc

        duration_ms = int((time.time() - start) * 1000)

        print("[ElevenLabsProvider] Синтез завершен успешно.")
        log_audit_entry(
            "elevenlabs_synthesis_success",
            "[ElevenLabsProvider/Synthesis] Синтез завершен успешно.",
            AuditStatus.INFO,
            details={
                "output_path": output_path,
                "duration_ms": duration_ms,
                "text_length": len(request.text),
            },
        )

        return TTSResult(
            success=True,
            provider=self.name,
            file_path=output_path,
            duration_ms=duration_ms,
        )
