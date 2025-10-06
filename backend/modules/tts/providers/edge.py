from __future__ import annotations
import os
import asyncio
import edge_tts
from .base import TTSProvider, TTSProviderError, TTSRequest, TTSResult


class EdgeTTSProvider(TTSProvider):
    def __init__(self, default_voice: str = "ru-RU-SvetlanaNeural"):
        self._default_voice = default_voice
        self._name = "edge"

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        # Простая проверка доступности
        try:
            import edge_tts

            return True
        except ImportError:
            return False

    def synthesize(self, request: TTSRequest, output_path: str) -> TTSResult:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return asyncio.run(self._async_synthesize(request, output_path))
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    print(f"Edge TTS попытка {attempt + 1} не удалась: {e}")
                    import time

                    time.sleep(wait_time)
                    continue
                else:
                    raise TTSProviderError(
                        f"Edge TTS failed after {max_retries} attempts: {e}"
                    )

    async def _async_synthesize(
        self, request: TTSRequest, output_path: str
    ) -> TTSResult:
        voice = request.voice or self._default_voice

        try:
            communicate = edge_tts.Communicate(request.text, voice=voice)
            await communicate.save(output_path)

            # Проверяем, что файл создан
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return TTSResult(
                    success=True, file_path=output_path, provider=self.name
                )
            else:
                raise TTSProviderError("Output file not created")

        except Exception as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise TTSProviderError(f"Edge TTS synthesis error: {e}")
