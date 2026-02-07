"""Voxtral/Mistral API client for audio transcription.

Uses httpx for async HTTP requests to the Mistral transcription API.
"""

import logging
from pathlib import Path
from typing import Optional

import httpx

from wayvoxtral.config import APIConfig, LanguageConfig

logger = logging.getLogger(__name__)


class VoxtralClient:
    """Async client for Mistral/Voxtral transcription API.

    Отправляет аудио файлы на API и получает транскрипцию.
    Поддерживает автоопределение языка и выбор конкретного языка.
    """

    TIMEOUT = 60.0  # Таймаут для API запросов (секунды)

    def __init__(
        self, api_config: APIConfig, language_config: LanguageConfig
    ) -> None:
        """Initialize the Voxtral client.

        Args:
            api_config: API configuration with key and endpoint
            language_config: Language settings
        """
        self.api_config = api_config
        self.language_config = language_config

    async def transcribe(
        self, audio_path: Path, language: Optional[str] = None
    ) -> str:
        """Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file (WAV format)
            language: Optional language code (e.g., 'ru', 'en').
                     If None, uses config settings.

        Returns:
            Transcribed text

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If API key is not configured
        """
        if not self.api_config.key:
            raise ValueError("Mistral API key not configured")

        # Определяем язык
        if language is None:
            if self.language_config.auto_detect:
                language = None  # Voxtral сам определит
            else:
                language = self.language_config.primary

        logger.info(
            f"Transcribing {audio_path.name} "
            f"(language: {language or 'auto-detect'})"
        )

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            # Читаем аудио файл
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            # Формируем multipart request
            files = {"file": (audio_path.name, audio_data, "audio/wav")}
            data: dict[str, str] = {"model": self.api_config.model}

            if language:
                data["language"] = language

            headers = {"Authorization": f"Bearer {self.api_config.key}"}

            logger.debug(f"Sending request to {self.api_config.endpoint}")

            response = await client.post(
                self.api_config.endpoint,
                files=files,
                data=data,
                headers=headers,
            )

            # Проверяем статус
            if response.status_code != 200:
                error_text = response.text
                logger.error(
                    f"API error: {response.status_code} - {error_text}"
                )
                response.raise_for_status()

            # Парсим ответ
            result = response.json()
            text = result.get("text", "")

            logger.info(f"Transcription complete: {len(text)} characters")
            return text

    async def check_connection(self) -> bool:
        """Check if the API is reachable (does not validate API key).

        Returns:
            True if API endpoint is reachable
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Просто проверяем что endpoint отвечает
                response = await client.options(self.api_config.endpoint)
                return response.status_code < 500
        except Exception as e:
            logger.warning(f"API connection check failed: {e}")
            return False
