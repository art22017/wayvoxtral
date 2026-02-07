"""Audio recording module using PyAudio.

Records audio from microphone to WAV file at 16kHz mono.
"""

import logging
import threading
import time
import wave
from pathlib import Path
from typing import Optional

import pyaudio

from wayvoxtral.config import AudioConfig

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Records audio from microphone to WAV file.

    Использует PyAudio для захвата аудио с микрофона.
    Записывает в формате 16kHz, mono, 16-bit PCM (требования Voxtral).
    """

    FORMAT = pyaudio.paInt16  # 16-bit
    SAMPLE_WIDTH = 2  # bytes per sample

    def __init__(self, config: AudioConfig) -> None:
        """Initialize the audio recorder.

        Args:
            config: Audio configuration settings
        """
        self.config = config
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._wave_file: Optional[wave.Wave_write] = None
        self._recording = False
        self._record_thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0
        self._current_path: Optional[Path] = None

    def _init_pyaudio(self) -> None:
        """Initialize PyAudio instance if not already done."""
        if self._pyaudio is None:
            self._pyaudio = pyaudio.PyAudio()

    def start_recording(self, path: Path) -> None:
        """Start recording audio to the specified WAV file.

        Args:
            path: Path to save the WAV file
        """
        if self._recording:
            logger.warning("Already recording, ignoring start request")
            return

        self._init_pyaudio()
        assert self._pyaudio is not None

        self._current_path = path
        self._recording = True
        self._start_time = time.time()

        # Открываем WAV файл для записи
        self._wave_file = wave.open(str(path), "wb")
        self._wave_file.setnchannels(self.config.channels)
        self._wave_file.setsampwidth(self.SAMPLE_WIDTH)
        self._wave_file.setframerate(self.config.sample_rate)

        # Открываем аудио поток
        self._stream = self._pyaudio.open(
            format=self.FORMAT,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            frames_per_buffer=self.config.chunk_size,
        )

        # Запускаем поток записи
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()

        logger.info(f"Started recording to {path}")

    def _record_loop(self) -> None:
        """Recording loop that runs in a separate thread."""
        try:
            while self._recording and self._stream is not None:
                # Проверяем максимальную длительность
                elapsed = time.time() - self._start_time
                if elapsed >= self.config.max_duration:
                    logger.warning(
                        f"Maximum recording duration ({self.config.max_duration}s) reached"
                    )
                    break

                # Читаем и записываем chunk
                try:
                    data = self._stream.read(
                        self.config.chunk_size, exception_on_overflow=False
                    )
                    if self._wave_file is not None:
                        self._wave_file.writeframes(data)
                except OSError as e:
                    logger.error(f"Audio read error: {e}")
                    break
        except Exception as e:
            logger.exception(f"Recording error: {e}")
        finally:
            self._recording = False

    def stop_recording(self) -> float:
        """Stop recording and return the duration in seconds.

        Returns:
            Duration of the recording in seconds
        """
        if not self._recording and self._record_thread is None:
            logger.warning("Not recording, ignoring stop request")
            return 0.0

        self._recording = False

        # Ждём завершения потока записи
        if self._record_thread is not None:
            self._record_thread.join(timeout=1.0)
            self._record_thread = None

        # Закрываем поток
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
            self._stream = None

        # Закрываем WAV файл
        if self._wave_file is not None:
            try:
                self._wave_file.close()
            except Exception as e:
                logger.error(f"Error closing wave file: {e}")
            self._wave_file = None

        duration = time.time() - self._start_time
        logger.info(f"Stopped recording. Duration: {duration:.2f}s")
        return duration

    def get_elapsed_time(self) -> float:
        """Get the elapsed recording time in seconds.

        Returns:
            Elapsed time in seconds, or 0 if not recording
        """
        if not self._recording:
            return 0.0
        return time.time() - self._start_time

    def is_recording(self) -> bool:
        """Check if currently recording.

        Returns:
            True if recording is in progress
        """
        return self._recording

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_recording()
        if self._pyaudio is not None:
            self._pyaudio.terminate()
            self._pyaudio = None
