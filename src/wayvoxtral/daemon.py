"""Main daemon for WayVoxtral.

Координирует все компоненты:
- Hotkey listener (evdev F24)
- Audio recording (PyAudio)
- API transcription (Mistral)
- Text insertion (ydotool)
- Overlay UI (GTK4)
"""

import asyncio
import logging
import tempfile
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from wayvoxtral.api import VoxtralClient
from wayvoxtral.audio import AudioRecorder
from wayvoxtral.config import Config
from wayvoxtral.hotkey import HotkeyListener
from wayvoxtral.insertion import copy_to_clipboard, insert_text
from wayvoxtral.ui import OverlayWindow

logger = logging.getLogger(__name__)


class DaemonState(Enum):
    """State machine states."""

    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    INSERTING = "inserting"


class WayVoxtralDaemon:
    """Main daemon that coordinates all components.

    State machine:
    IDLE -> RECORDING (on first hotkey)
    RECORDING -> PROCESSING (on second hotkey)
    PROCESSING -> INSERTING (on API response)
    INSERTING -> IDLE (after text insertion)
    """

    def __init__(self) -> None:
        """Initialize the daemon."""
        self._state = DaemonState.IDLE
        self._config: Optional[Config] = None
        self._audio_recorder: Optional[AudioRecorder] = None
        self._api_client: Optional[VoxtralClient] = None
        self._hotkey_listener: Optional[HotkeyListener] = None
        self._overlay: Optional[OverlayWindow] = None
        self._app: Optional[Gtk.Application] = None
        self._current_audio_path: Optional[Path] = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            self._config = Config.load()
            logger.info("Configuration loaded")

            if not self._config.api.key:
                logger.warning(
                    "API key not configured! "
                    "Edit ~/.config/wayvoxtral/config.json"
                )
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = Config()

    def _init_components(self) -> None:
        """Initialize all components."""
        assert self._config is not None

        self._audio_recorder = AudioRecorder(self._config.audio)
        self._api_client = VoxtralClient(
            self._config.api, self._config.languages
        )
        self._hotkey_listener = HotkeyListener()

        logger.info("Components initialized")

    def run(self) -> None:
        """Run the daemon with GTK main loop."""
        self._load_config()
        self._init_components()

        # Создаём GTK Application
        self._app = Gtk.Application(application_id="com.wayvoxtral.daemon")
        self._app.connect("activate", self._on_activate)

        # Запускаем
        self._app.run(None)

    def _on_activate(self, app: Gtk.Application) -> None:
        """GTK application activate handler."""
        # Создаём overlay window
        self._overlay = OverlayWindow(app)

        # Запускаем async event loop в отдельном потоке
        # GTK main loop будет работать в основном потоке
        self._start_async_loop()

        logger.info("WayVoxtral daemon ready. Press Ctrl+Space to start recording.")

    def _start_async_loop(self) -> None:
        """Start async event loop for hotkey listening."""
        import threading

        def run_async():
            self._main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._main_loop)
            self._main_loop.run_until_complete(self._hotkey_loop())

        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()

    async def _hotkey_loop(self) -> None:
        """Main async loop for hotkey handling."""
        assert self._hotkey_listener is not None

        logger.info("Hotkey listener started")

        async for _ in self._hotkey_listener.listen():
            logger.debug(f"Hotkey triggered, state: {self._state}")

            if self._state == DaemonState.IDLE:
                self._start_recording()
            elif self._state == DaemonState.RECORDING:
                await self._stop_recording_and_transcribe()
            # В других состояниях игнорируем hotkey

    def _start_recording(self) -> None:
        """Start audio recording."""
        assert self._audio_recorder is not None
        assert self._overlay is not None

        self._state = DaemonState.RECORDING

        # Создаём временный файл
        temp_dir = Path(tempfile.gettempdir())
        self._current_audio_path = temp_dir / f"wayvoxtral_{uuid.uuid4().hex}.wav"

        # Запускаем запись
        self._audio_recorder.start_recording(self._current_audio_path)

        # Показываем UI (через GLib.idle_add для thread-safety)
        GLib.idle_add(self._overlay.show_recording, 0)

        # Запускаем обновление UI каждую секунду
        GLib.timeout_add(1000, self._update_recording_ui)

        logger.info("Recording started")

    def _update_recording_ui(self) -> bool:
        """Update recording UI with elapsed time.

        Returns:
            True to continue timer, False to stop
        """
        if self._state != DaemonState.RECORDING:
            return False

        if self._audio_recorder is not None and self._overlay is not None:
            elapsed = int(self._audio_recorder.get_elapsed_time())
            GLib.idle_add(self._overlay.show_recording, elapsed)

        return True

    async def _stop_recording_and_transcribe(self) -> None:
        """Stop recording and send to API."""
        assert self._audio_recorder is not None
        assert self._api_client is not None
        assert self._overlay is not None
        assert self._config is not None

        # Останавливаем запись
        duration = self._audio_recorder.stop_recording()
        logger.info(f"Recording stopped, duration: {duration:.2f}s")

        if duration < 0.5:
            logger.warning("Recording too short, discarding")
            self._cleanup_and_idle()
            GLib.idle_add(self._overlay.show_error, "Recording too short")
            return

        self._state = DaemonState.PROCESSING

        # Показываем processing UI
        GLib.idle_add(self._overlay.show_processing)

        # Отправляем на API
        try:
            assert self._current_audio_path is not None
            text = await self._api_client.transcribe(self._current_audio_path)

            if not text.strip():
                raise ValueError("Empty transcription received")

            logger.info(f"Transcription: {text[:50]}...")

            # Вставляем текст
            self._state = DaemonState.INSERTING
            self._insert_transcription(text)

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            GLib.idle_add(self._overlay.show_error, str(e)[:50])

        finally:
            self._cleanup_and_idle()

    def _insert_transcription(self, text: str) -> None:
        """Insert transcribed text into active window."""
        assert self._overlay is not None
        assert self._config is not None

        success = False

        # Копируем в буфер обмена
        if self._config.behavior.copy_to_clipboard:
            copy_to_clipboard(text)

        # Вставляем текст
        if self._config.behavior.auto_paste:
            success = insert_text(text)

        if success:
            GLib.idle_add(self._overlay.show_result, text)
            logger.info("Text inserted successfully")
        else:
            GLib.idle_add(
                self._overlay.show_error,
                "Failed to insert text. Check ydotool."
            )

    def _cleanup_and_idle(self) -> None:
        """Clean up temporary files and return to idle state."""
        # Удаляем временный файл
        if self._current_audio_path is not None:
            try:
                self._current_audio_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")
            self._current_audio_path = None

        self._state = DaemonState.IDLE

    def cleanup(self) -> None:
        """Clean up all resources."""
        if self._audio_recorder is not None:
            self._audio_recorder.cleanup()

        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()

        self._cleanup_and_idle()
        logger.info("Daemon cleanup complete")
