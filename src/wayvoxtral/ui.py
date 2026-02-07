"""GTK4 Overlay UI for WayVoxtral.

Displays a floating overlay window showing recording/processing status.
GNOME-compatible: uses standard GTK4 window with transparency (no Layer Shell).
"""

import logging
from enum import Enum
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

logger = logging.getLogger(__name__)


class OverlayState(Enum):
    """Overlay window states."""

    HIDDEN = "hidden"
    RECORDING = "recording"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


# CSS стили для overlay
OVERLAY_CSS = """
window.overlay {
    background: rgba(0, 0, 0, 0.85);
    border-radius: 24px;
    padding: 12px 20px;
}

window.overlay label {
    color: white;
    font-size: 14px;
    font-weight: 500;
    font-family: "Inter", "SF Pro Display", system-ui, sans-serif;
}

window.overlay.recording label {
    color: #4ade80;
}

window.overlay.processing label {
    color: #60a5fa;
}

window.overlay.success label {
    color: #10b981;
}

window.overlay.error label {
    color: #ef4444;
}

@keyframes pulse {
    0%, 100% { opacity: 1.0; }
    50% { opacity: 0.6; }
}

.pulsing {
    animation: pulse 1.5s infinite;
}
"""


class OverlayWindow(Gtk.Window):
    """Floating overlay window for status display.

    Отображает состояние записи/обработки в стиле Dynamic Island.
    Работает на GNOME Wayland без Layer Shell.
    """

    def __init__(self, app: Gtk.Application) -> None:
        """Initialize the overlay window.

        Args:
            app: GTK Application instance
        """
        super().__init__(application=app)

        self._state = OverlayState.HIDDEN
        self._timer_id: Optional[int] = None
        self._auto_hide_id: Optional[int] = None
        self._elapsed_seconds = 0

        self._setup_window()
        self._setup_css()
        self._setup_widgets()

    def _setup_window(self) -> None:
        """Configure window properties."""
        # Без декораций
        self.set_decorated(False)

        # Размеры
        self.set_default_size(280, 48)
        self.set_resizable(False)

        # Всегда сверху (hint для compositor)
        # На GNOME это не гарантировано, но работает для большинства случаев

        # CSS класс
        self.add_css_class("overlay")

        # Подключаемся к сигналу realize для позиционирования
        self.connect("realize", self._on_realize)

    def _setup_css(self) -> None:
        """Load CSS styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(OVERLAY_CSS)

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _setup_widgets(self) -> None:
        """Create UI widgets."""
        # Основной контейнер
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        # Spinner для processing
        self._spinner = Gtk.Spinner()
        self._spinner.set_visible(False)
        box.append(self._spinner)

        # Основной label
        self._label = Gtk.Label()
        self._label.set_halign(Gtk.Align.CENTER)
        box.append(self._label)

        self.set_child(box)

    def _on_realize(self, widget: Gtk.Widget) -> None:
        """Position window after it's realized."""
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        """Position window at top-center of screen."""
        display = Gdk.Display.get_default()
        if not display:
            return

        # Получаем монитор
        monitors = display.get_monitors()
        if monitors.get_n_items() == 0:
            return

        monitor = monitors.get_item(0)
        if not monitor:
            return

        geometry = monitor.get_geometry()

        # Позиционируем по центру сверху
        # Примечание: на Wayland позиционирование окон ограничено compositor
        # Это работает как hint, но может быть проигнорировано
        window_width = self.get_width()
        x = geometry.x + (geometry.width - window_width) // 2
        y = geometry.y + 40  # Отступ от верха

        # На GTK4 + Wayland прямое позиционирование не гарантируется
        # Но мы устанавливаем hint

    def show_recording(self, seconds: int = 0) -> None:
        """Show recording state.

        Args:
            seconds: Elapsed recording time in seconds
        """
        self._state = OverlayState.RECORDING
        self._elapsed_seconds = seconds

        # Обновляем стили
        self._clear_state_classes()
        self.add_css_class("recording")
        self._label.add_css_class("pulsing")

        # Обновляем текст
        self._update_recording_label()

        # Показываем окно
        self._spinner.set_visible(False)
        self._spinner.stop()
        self.set_visible(True)
        self.present()

        # Запускаем таймер обновления
        if self._timer_id is None:
            self._timer_id = GLib.timeout_add(1000, self._on_timer_tick)

    def _update_recording_label(self) -> None:
        """Update the recording label with current time."""
        minutes = self._elapsed_seconds // 60
        secs = self._elapsed_seconds % 60
        self._label.set_text(f"🎙️  Recording... [{minutes}:{secs:02d}]")

    def _on_timer_tick(self) -> bool:
        """Timer callback for updating recording time.

        Returns:
            True to continue timer, False to stop
        """
        if self._state != OverlayState.RECORDING:
            self._timer_id = None
            return False

        self._elapsed_seconds += 1
        self._update_recording_label()
        return True

    def show_processing(self) -> None:
        """Show processing state."""
        self._stop_timer()
        self._state = OverlayState.PROCESSING

        self._clear_state_classes()
        self.add_css_class("processing")
        self._label.remove_css_class("pulsing")

        self._label.set_text("⏳  Processing...")
        self._spinner.set_visible(True)
        self._spinner.start()

        self.set_visible(True)
        self.present()

    def show_result(self, text: str, auto_hide_ms: int = 1500) -> None:
        """Show success result.

        Args:
            text: Transcribed text to display
            auto_hide_ms: Time before auto-hide in milliseconds
        """
        self._stop_timer()
        self._state = OverlayState.SUCCESS

        self._clear_state_classes()
        self.add_css_class("success")
        self._label.remove_css_class("pulsing")

        # Обрезаем длинный текст
        preview = text[:40] + "..." if len(text) > 40 else text
        self._label.set_text(f"✓  {preview}")

        self._spinner.set_visible(False)
        self._spinner.stop()

        self.set_visible(True)
        self.present()

        # Auto-hide
        self._schedule_auto_hide(auto_hide_ms)

    def show_error(self, message: str, auto_hide_ms: int = 3000) -> None:
        """Show error state.

        Args:
            message: Error message to display
            auto_hide_ms: Time before auto-hide in milliseconds
        """
        self._stop_timer()
        self._state = OverlayState.ERROR

        self._clear_state_classes()
        self.add_css_class("error")
        self._label.remove_css_class("pulsing")

        # Обрезаем длинное сообщение
        short_msg = message[:50] + "..." if len(message) > 50 else message
        self._label.set_text(f"❌  {short_msg}")

        self._spinner.set_visible(False)
        self._spinner.stop()

        self.set_visible(True)
        self.present()

        # Auto-hide
        self._schedule_auto_hide(auto_hide_ms)

    def hide_overlay(self) -> None:
        """Hide the overlay window."""
        self._stop_timer()
        self._cancel_auto_hide()
        self._state = OverlayState.HIDDEN
        self._elapsed_seconds = 0
        self.set_visible(False)

    def _clear_state_classes(self) -> None:
        """Remove all state CSS classes."""
        for state in OverlayState:
            if state != OverlayState.HIDDEN:
                self.remove_css_class(state.value)

    def _stop_timer(self) -> None:
        """Stop the recording timer."""
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _schedule_auto_hide(self, delay_ms: int) -> None:
        """Schedule auto-hide after delay.

        Args:
            delay_ms: Delay in milliseconds
        """
        self._cancel_auto_hide()
        self._auto_hide_id = GLib.timeout_add(delay_ms, self._on_auto_hide)

    def _cancel_auto_hide(self) -> None:
        """Cancel pending auto-hide."""
        if self._auto_hide_id is not None:
            GLib.source_remove(self._auto_hide_id)
            self._auto_hide_id = None

    def _on_auto_hide(self) -> bool:
        """Auto-hide callback.

        Returns:
            False to stop the timeout
        """
        self._auto_hide_id = None
        self.hide_overlay()
        return False

    def get_state(self) -> OverlayState:
        """Get current overlay state.

        Returns:
            Current OverlayState
        """
        return self._state
