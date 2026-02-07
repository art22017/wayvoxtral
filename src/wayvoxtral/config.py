"""Configuration models for WayVoxtral.

Uses Pydantic for validation and settings management.
Config file: ~/.config/wayvoxtral/config.json
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIConfig(BaseModel):
    """Mistral/Voxtral API configuration."""

    key: str = Field(default="", description="Mistral API key")
    model: str = Field(
        default="mistral-small-latest",
        description="Voxtral model for transcription",
    )
    endpoint: str = Field(
        default="https://api.mistral.ai/v1/audio/transcriptions",
        description="Transcription API endpoint",
    )


class LanguageConfig(BaseModel):
    """Language detection and preference settings."""

    auto_detect: bool = Field(default=True, description="Auto-detect language")
    preferred: list[str] = Field(
        default=["ru", "en"], description="Preferred languages for detection"
    )
    primary: str = Field(
        default="ru", description="Primary language if auto-detect is off"
    )


class HotkeyConfig(BaseModel):
    """Hotkey configuration."""

    toggle: str = Field(
        default="ctrl+space", description="Toggle recording hotkey"
    )


class AudioConfig(BaseModel):
    """Audio recording settings."""

    sample_rate: int = Field(default=16000, description="Sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    format: Literal["wav"] = Field(default="wav", description="Audio format")
    chunk_size: int = Field(default=2048, description="Audio chunk size in frames")
    max_duration: int = Field(
        default=30, description="Maximum recording duration in seconds"
    )


class UIConfig(BaseModel):
    """UI appearance settings."""

    theme: Literal["dark", "light"] = Field(default="dark", description="UI theme")
    position: Literal["top-center", "top-left", "top-right"] = Field(
        default="top-center", description="Overlay position"
    )
    animation_duration_ms: int = Field(
        default=200, description="Animation duration in milliseconds"
    )


class BehaviorConfig(BaseModel):
    """Application behavior settings."""

    auto_paste: bool = Field(
        default=True, description="Automatically paste transcription"
    )
    copy_to_clipboard: bool = Field(
        default=True, description="Copy transcription to clipboard"
    )
    show_notification: bool = Field(
        default=False, description="Show desktop notification"
    )


class Config(BaseSettings):
    """Root configuration for WayVoxtral.

    Loads from ~/.config/wayvoxtral/config.json
    """

    model_config = SettingsConfigDict(
        json_file=Path.home() / ".config" / "wayvoxtral" / "config.json",
        json_file_encoding="utf-8",
        extra="ignore",
    )

    api: APIConfig = Field(default_factory=APIConfig)
    languages: LanguageConfig = Field(default_factory=LanguageConfig)
    hotkeys: HotkeyConfig = Field(default_factory=HotkeyConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file, creating defaults if needed."""
        config_path = Path.home() / ".config" / "wayvoxtral" / "config.json"

        if not config_path.exists():
            # Создаём директорию и дефолтный конфиг
            config_path.parent.mkdir(parents=True, exist_ok=True)
            default_config = cls()
            config_path.write_text(
                default_config.model_dump_json(indent=2), encoding="utf-8"
            )
            return default_config

        # Загружаем из файла
        import json

        data = json.loads(config_path.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def save(self) -> None:
        """Save current configuration to file."""
        config_path = Path.home() / ".config" / "wayvoxtral" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
