"""Global hotkey listener using evdev.

Monitors keyboard input for F24 keypress (mapped from Ctrl+Space by keyd).
Works at kernel level, bypassing Wayland security restrictions.
"""

import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional

import evdev
from evdev import InputDevice, categorize, ecodes

logger = logging.getLogger(__name__)

# F24 - глобальный хоткей для WayVoxtral (mapped from Ctrl+Space by keyd)
TARGET_KEY = ecodes.KEY_F24


class HotkeyListener:
    """Listens for global hotkey events using evdev.

    Мониторит /dev/input/eventX устройства для отслеживания F24 keypress.
    keyd преобразует Ctrl+Space в F24 на системном уровне.
    """

    def __init__(self) -> None:
        """Initialize the hotkey listener."""
        self._devices: list[InputDevice] = []
        self._running = False

    def _find_keyboard_devices(self) -> list[InputDevice]:
        """Find all keyboard input devices.

        Returns:
            List of keyboard input devices
        """
        devices = []
        input_path = Path("/dev/input")

        for event_file in input_path.glob("event*"):
            try:
                device = InputDevice(str(event_file))
                capabilities = device.capabilities()
                if ecodes.EV_KEY in capabilities:
                    key_caps = capabilities[ecodes.EV_KEY]
                    # Ищем клавиатуры с F9
                    if ecodes.KEY_F9 in key_caps:
                        devices.append(device)
                        logger.debug(f"Found keyboard: {device.name}")
            except (OSError, PermissionError) as e:
                logger.debug(f"Cannot access {event_file}: {e}")
                continue

        return devices

    async def wait_for_trigger(self) -> None:
        """Wait for a single hotkey trigger (F9 keypress).

        Blocks until F9 key is pressed and released.
        """
        devices = self._find_keyboard_devices()

        if not devices:
            logger.warning("No standard keyboards found. Checking all input devices.")
            devices = self._find_all_keyboards()

        if not devices:
            raise RuntimeError(
                "No input devices found. "
                "Add user to 'input' group: sudo usermod -aG input $USER"
            )

        logger.info(f"Monitoring {len(devices)} device(s) for F9 keypress")
        
        # Создаём async readers для всех устройств
        loop = asyncio.get_event_loop()
        readers: dict[int, InputDevice] = {}

        for device in devices:
            try:
                fd = device.fd
                loop.add_reader(fd, lambda: None)  # Регистрируем для select
                readers[fd] = device
                logger.debug(f"Monitoring {device.name} at {device.path}")
            except Exception as e:
                logger.warning(f"Failed to monitor device {device.name}: {e}")

        try:
            while True:
                # Ждём события на любом устройстве
                await asyncio.sleep(0.01)

                for fd, device in readers.items():
                    try:
                        while True:
                            # Читаем все доступные события
                            try:
                                for event in device.read():
                                    if event.type == ecodes.EV_KEY:
                                        key_event = categorize(event)
                                        # KEY_DOWN = 1
                                        if key_event.keystate == 1:
                                            # logger.debug(f"Key detected: {key_event.keycode} ({key_event.scancode}) on {device.name}")
                                            if key_event.scancode == TARGET_KEY:
                                                logger.info("Hotkey (F9) detected!")
                                                return
                            except BlockingIOError:
                                break
                    except (OSError, Exception) as e:
                        logger.error(f"Error reading device: {e}")
                        await asyncio.sleep(0.1)
                        continue

        finally:
            # Убираем readers
            for fd in readers:
                try:
                    loop.remove_reader(fd)
                except ValueError:
                    pass

    def _find_all_keyboards(self) -> list[InputDevice]:
        """Find all keyboard devices (fallback method).

        Returns:
            List of all keyboard input devices
        """
        devices = []
        input_path = Path("/dev/input")

        for event_file in input_path.glob("event*"):
            try:
                device = InputDevice(str(event_file))
                capabilities = device.capabilities()
                if ecodes.EV_KEY in capabilities:
                    # Проверяем наличие обычных клавиш (A-Z)
                    key_caps = capabilities[ecodes.EV_KEY]
                    if ecodes.KEY_A in key_caps:
                        devices.append(device)
            except (OSError, PermissionError):
                continue

        return devices

    async def listen(self) -> AsyncGenerator[None, None]:
        """Async generator that yields on each hotkey trigger.

        Yields:
            None on each hotkey press
        """
        self._running = True

        while self._running:
            try:
                await self.wait_for_trigger()
                yield
            except Exception as e:
                logger.error(f"Hotkey listener error: {e}")
                await asyncio.sleep(1.0)  # Backoff on error

    def stop(self) -> None:
        """Stop the hotkey listener."""
        self._running = False
