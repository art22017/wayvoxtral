"""Groq API client for audio transcription.

Uses AsyncGroq SDK for transcription.
"""

import logging
import time
from pathlib import Path
from typing import Optional

import httpx
from groq import AsyncGroq, APIConnectionError, APIStatusError, DefaultAsyncHttpxClient

from wayvoxtral.config import APIConfig, LanguageConfig

logger = logging.getLogger(__name__)


class VoxtralClient:
    """Async client for Groq Whisper transcription API."""

    def __init__(
        self, api_config: APIConfig, language_config: LanguageConfig
    ) -> None:
        """Initialize the Groq client.

        Args:
            api_config: API configuration with key
            language_config: Language settings
        """
        self.api_config = api_config
        self.language_config = language_config
        self._client: Optional[AsyncGroq] = None

    def _get_client(self) -> AsyncGroq:
        if not self._client:
            if not self.api_config.key:
                raise ValueError("Groq API key not configured")
            
            # Настройка http клиента с прокси
            # Используем httpx.AsyncClient напрямую
            # В httpx 0.28.0+ аргумент proxies заменен на proxy (singular)
            http_client = httpx.AsyncClient(
                proxy=self.api_config.proxy,
                transport=httpx.AsyncHTTPTransport(retries=3)
            )

            # Если указан кастомный endpoint (редко для Groq, но всё же)
            base_url = self.api_config.endpoint if self.api_config.endpoint else None
            
            logger.info(f"Initializing Groq client with proxy: {self.api_config.proxy}")
            
            self._client = AsyncGroq(
                api_key=self.api_config.key,
                base_url=base_url,
                http_client=http_client
            )
        return self._client

    async def transcribe(
        self, audio_path: Path, language: Optional[str] = None
    ) -> str:
        """Transcribe an audio file to text using Groq Whisper.

        Args:
            audio_path: Path to the audio file (WAV format)
            language: Optional language code (e.g., 'ru', 'en').
                     If None, uses config settings.

        Returns:
            Transcribed text
        """
        client = self._get_client()

        # Определяем язык
        if language is None:
            if self.language_config.auto_detect:
                language = None  # Whisper сам определит
            else:
                language = self.language_config.primary

        model = self.api_config.model
        logger.info(
            f"Transcribing {audio_path.name} via Groq\n"
            f"  Model: {model}\n"
            f"  Language: {language or 'auto-detect'}\n"
            f"  File size: {audio_path.stat().st_size / 1024:.2f} KB\n"
            f"  Proxy: {self.api_config.proxy}"
        )

        start_time = time.time()
        try:
            with open(audio_path, "rb") as file:
                # Читаем файл в память для отправки
                file_content = file.read()
                
            logger.debug(f"Sending request to Groq API...")
            
            transcription = await client.audio.transcriptions.create(
                file=(audio_path.name, file_content),
                model=model,
                language=language,
                temperature=0.0,
                response_format="verbose_json",
            )
            
            duration = time.time() - start_time
            text = transcription.text
            
            logger.info(
                f"Transcription complete in {duration:.2f}s\n"
                f"  Chars: {len(text)}\n"
                f"  Text preview: {text[:100]}..."
            )
            
            return text

        except APIConnectionError as e:
            logger.error(f"Groq API connection error: {e}")
            logger.error(f"Check your internet connection and proxy settings ({self.api_config.proxy})")
            raise RuntimeError("API connection failed. Check internet/proxy.")
        except APIStatusError as e:
            logger.error(f"Groq API status error: {e.status_code} - {e.message}")
            raise RuntimeError(f"API Error {e.status_code}: {e.message}")
        except Exception as e:
            logger.exception(f"Unexpected error during transcription: {e}")
            raise RuntimeError(f"Transcription failed: {e}")

    async def check_connection(self) -> bool:
        """Check if the API client can be initialized."""
        try:
            self._get_client()
            return True
        except ValueError:
            return False
