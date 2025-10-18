from __future__ import annotations

import time
from typing import Dict

import requests

from modules.tts.providers.base import TTSProvider, TTSProviderError
from modules.tts.types import TTSRequest, TTSResult
from services.logger_service import AuditStatus, log_audit_entry
from services.localization_service import get_text


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"

    def __init__(self, config: Dict[str, any]) -> None:
        self._config = config or {}
        message_init = get_text(
            "logger.elevenlabs_provider_init",
            default="[ElevenLabsProvider] Провайдер ElevenLabs инициализирован.",
        )
        print(message_init)
        log_audit_entry(
            "elevenlabs_provider_init",
            message_init,
            AuditStatus.INFO,
            details={
                "has_api_key": bool(self._config.get("api_key")),
                "has_voice_id": bool(self._config.get("voice_id")),
                "model_id": self._config.get("model_id"),
                "stability": self._config.get("stability"),
                "similarity": self._config.get("similarity"),
            },
            message_key="logger.elevenlabs_provider_init",
        )

    def is_available(self) -> bool:
        available = bool(self._config.get("api_key") and self._config.get("voice_id"))
        print(
            get_text(
                "elevenlabs.print_availability",
                params={"available": available},
                default=f"[ElevenLabsProvider] Проверка доступности провайдера: {available}.",
            )
        )
        log_message = get_text(
            "logger.elevenlabs_availability_check",
            default="[ElevenLabsProvider] Проверка доступности провайдера.",
        )
        log_audit_entry(
            "elevenlabs_availability_check",
            log_message,
            AuditStatus.INFO if available else AuditStatus.WARNING,
            details={
                "has_api_key": bool(self._config.get("api_key")),
                "has_voice_id": bool(self._config.get("voice_id")),
            },
            message_key="logger.elevenlabs_availability_check",
            message_args={"available": available},
        )
        return available

    def synthesize(self, request: TTSRequest, output_path: str) -> TTSResult:
        api_key = self._config.get("api_key")
        voice_id = self._config.get("voice_id")
        model_id = self._config.get("model_id", "eleven_multilingual_v2")
        stability = self._config.get("stability", 0.5)
        similarity = self._config.get("similarity", 0.75)

        message_start = get_text(
            "logger.elevenlabs_synthesis_start",
            default="[ElevenLabsProvider] Начало синтеза текста в речь.",
        )
        print(message_start)
        log_audit_entry(
            "elevenlabs_synthesis_start",
            message_start,
            AuditStatus.INFO,
            details={
                "text_length": len(request.text),
                "voice_id": voice_id,
                "model_id": model_id,
                "stability": stability,
                "similarity": similarity,
                "output_path": output_path,
            },
            message_key="logger.elevenlabs_synthesis_start",
        )

        if not api_key or not voice_id:
            message_config_error = get_text(
                "logger.elevenlabs_config_error",
                default="[ElevenLabsProvider] Отсутствует API-ключ или ID голоса.",
            )
            print(message_config_error)
            log_audit_entry(
                "elevenlabs_config_error",
                message_config_error,
                AuditStatus.ERROR,
                details={"has_api_key": bool(api_key), "has_voice_id": bool(voice_id)},
                message_key="logger.elevenlabs_config_error",
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
        message_request_prepared = get_text(
            "logger.elevenlabs_request_prepared",
            default="[ElevenLabsProvider] Запрос подготовлен для отправки.",
        )
        print(message_request_prepared)
        log_audit_entry(
            "elevenlabs_request_prepared",
            message_request_prepared,
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
            message_key="logger.elevenlabs_request_prepared",
        )

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        start = time.time()
        try:
            message_request_sent = get_text(
                "logger.elevenlabs_request_sent",
                params={"url": url},
                default="[ElevenLabsProvider] Запрос отправлен на API.",
            )
            print(message_request_sent)
            log_audit_entry(
                "elevenlabs_request_sent",
                message_request_sent,
                AuditStatus.INFO,
                details={"url": url, "method": "POST", "timeout": 60},
                message_key="logger.elevenlabs_request_sent",
                message_args={"url": url},
            )

            response = requests.post(
                url, headers=headers, json=payload, stream=True, timeout=60
            )

            print(
                get_text(
                    "elevenlabs.print_response_status",
                    params={"status_code": response.status_code},
                    default=f"[ElevenLabsProvider] Получен ответ от API: {response.status_code}",
                )
            )
            response_log_message = get_text(
                "logger.elevenlabs_response_received",
                params={"status_code": response.status_code},
                default="[ElevenLabsProvider] Ответ получен от API.",
            )
            log_audit_entry(
                "elevenlabs_response_received",
                response_log_message,
                AuditStatus.INFO,
                details={
                    "status_code": response.status_code,
                    "content_length": response.headers.get("content-length"),
                    "content_type": response.headers.get("content-type"),
                    "response_headers": dict(response.headers),
                },
                message_key="logger.elevenlabs_response_received",
                message_args={"status_code": response.status_code},
            )

            if response.status_code == 200:
                message_download_start = get_text(
                    "logger.elevenlabs_downloading_audio",
                    params={"output_path": output_path},
                    default="[ElevenLabsProvider] Начало загрузки аудиофайла.",
                )
                print(message_download_start)
                log_audit_entry(
                    "elevenlabs_downloading_audio",
                    message_download_start,
                    AuditStatus.INFO,
                    details={
                        "output_path": output_path,
                        "content_length": response.headers.get("content-length"),
                    },
                    message_key="logger.elevenlabs_downloading_audio",
                    message_args={"output_path": output_path},
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
                                progress_message = get_text(
                                    "elevenlabs.print_download_progress",
                                    params={"chunk_number": chunk_count},
                                    default=f"[ElevenLabsProvider] Прогресс загрузки: {chunk_count} чанков.",
                                )
                                print(progress_message)
                                log_progress = get_text(
                                    "logger.elevenlabs_download_progress",
                                    params={
                                        "chunk_number": chunk_count,
                                        "bytes_downloaded": total_bytes,
                                    },
                                    default="[ElevenLabsProvider/Download] Прогресс загрузки.",
                                )
                                log_audit_entry(
                                    "elevenlabs_download_progress",
                                    log_progress,
                                    AuditStatus.INFO,
                                    details={
                                        "chunk_number": chunk_count,
                                        "bytes_downloaded": total_bytes,
                                        "chunk_size": len(chunk),
                                    },
                                    message_key="logger.elevenlabs_download_progress",
                                    message_args={
                                        "chunk_number": chunk_count,
                                        "bytes_downloaded": total_bytes,
                                    },
                                )

                message_download_complete = get_text(
                    "logger.elevenlabs_download_completed",
                    params={
                        "chunks_count": chunk_count,
                        "total_bytes": total_bytes,
                    },
                    default="[ElevenLabsProvider] Загрузка аудиофайла завершена.",
                )
                print(message_download_complete)
                log_audit_entry(
                    "elevenlabs_download_completed",
                    message_download_complete,
                    AuditStatus.INFO,
                    details={
                        "output_path": output_path,
                        "total_bytes": total_bytes,
                        "chunks_count": chunk_count,
                    },
                    message_key="logger.elevenlabs_download_completed",
                    message_args={
                        "chunks_count": chunk_count,
                        "total_bytes": total_bytes,
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

                error_message = get_text(
                    "logger.elevenlabs_api_error",
                    params={"status_code": response.status_code},
                    default=f"[ElevenLabsProvider] API вернул ошибку {response.status_code}.",
                )
                print(error_message)
                log_audit_entry(
                    "elevenlabs_api_error",
                    error_message,
                    AuditStatus.ERROR,
                    details=error_details,
                    message_args={"status_code": response.status_code},
                    message_key="logger.elevenlabs_api_error",
                )

                raise TTSProviderError(
                    f"ElevenLabs API error {response.status_code}: {response.text}"
                )
        except requests.exceptions.Timeout:
            timeout_message = get_text(
                "logger.elevenlabs_request_timeout",
                params={"timeout": 60},
                default="[ElevenLabsProvider] Запрос истек по времени.",
            )
            print(timeout_message)
            log_audit_entry(
                "elevenlabs_request_timeout",
                timeout_message,
                AuditStatus.ERROR,
                details={"timeout_value": 60, "url": url},
                message_key="logger.elevenlabs_request_timeout",
                message_args={"timeout": 60},
            )
            raise TTSProviderError("ElevenLabs request timed out after 60 seconds")
        except requests.exceptions.ConnectionError as e:
            connection_message = get_text(
                "elevenlabs.print_connection_error",
                params={"error": str(e)},
                default=f"[ElevenLabsProvider] Ошибка подключения: {e}",
            )
            print(connection_message)
            log_connection = get_text(
                "logger.elevenlabs_connection_error",
                params={"error": str(e)},
                default="[ElevenLabsProvider] Произошла ошибка подключения.",
            )
            log_audit_entry(
                "elevenlabs_connection_error",
                log_connection,
                AuditStatus.ERROR,
                details={"error": str(e), "url": url},
                message_key="logger.elevenlabs_connection_error",
                message_args={"error": str(e)},
            )
            raise TTSProviderError(f"ElevenLabs connection error: {e}")
        except Exception as exc:
            print(
                get_text(
                    "elevenlabs.print_synthesis_exception",
                    params={"error": str(exc)},
                    default=f"[ElevenLabsProvider] Синтез завершился с ошибкой: {exc}",
                )
            )
            failure_message = get_text(
                "logger.elevenlabs_synthesis_failed",
                params={"error": str(exc)},
                default="[ElevenLabsProvider] Синтез завершился с ошибкой.",
            )
            log_audit_entry(
                "elevenlabs_synthesis_failed",
                failure_message,
                AuditStatus.ERROR,
                details={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "url": url,
                },
                message_key="logger.elevenlabs_synthesis_failed",
                message_args={"error": str(exc)},
            )
            raise TTSProviderError(f"ElevenLabs synthesis failed: {exc}") from exc

        duration_ms = int((time.time() - start) * 1000)

        success_message = get_text(
            "logger.elevenlabs_synthesis_success",
            params={"duration_ms": duration_ms},
            default="[ElevenLabsProvider] Синтез завершен успешно.",
        )
        print(success_message)
        log_audit_entry(
            "elevenlabs_synthesis_success",
            success_message,
            AuditStatus.INFO,
            details={
                "output_path": output_path,
                "duration_ms": duration_ms,
                "text_length": len(request.text),
            },
            message_key="logger.elevenlabs_synthesis_success",
            message_args={"duration_ms": duration_ms},
        )

        return TTSResult(
            success=True,
            provider=self.name,
            file_path=output_path,
            duration_ms=duration_ms,
        )
