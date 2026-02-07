# WayVoxtral

**Push-to-Speech** tool for Wayland with global hotkey support, Mistral Voxtral transcription, and overlay UI.

## Features

- 🎙️ **Global Hotkey**: Ctrl+Space works in any application (via keyd)
- 🌍 **Multilingual**: Russian + English auto-detection
- ⚡ **Low Latency**: ~2-3 seconds from speech to text
- 🖥️ **Wayland Native**: Works on GNOME, no X11 required
- 🎨 **Overlay UI**: Dynamic Island-style status display

# Quick Start

> [!IMPORTANT]
> **CRITICAL STEP:** After running the installer, you **MUST** log out and back in. This is required for group permissions (input) to take effect.

```bash
# Clone the repo
git clone https://github.com/wayvoxtral/wayvoxtral.git
cd wayvoxtral

# Run installer (requires sudo)
bash scripts/install.sh

# 1. LOG OUT AND LOG BACK IN (REQUIRED!)

# 2. Add your Mistral API key
nano ~/.config/wayvoxtral/config.json

# 3. Start the service
systemctl --user start wayvoxtral
```

## Usage

1. **Press F9** - Start recording (overlay shows "Recording...")
2. **Speak** - Up to 30 seconds
3. **Press F9 again** - Stop and transcribe
4. **Text appears** in the active application

## Requirements

- Ubuntu 24.04+ with Wayland (GNOME)
- Microphone
- Groq API key ([get one here](https://console.groq.com/keys))

## Configuration

Edit `~/.config/wayvoxtral/config.json`:

```json
{
  "api": {
    "key": "YOUR_GROQ_API_KEY",
    "model": "whisper-large-v3",
    "proxy": "http://127.0.0.1:2080"
  },
  "languages": {
    "auto_detect": true,
    "primary": "ru"
  }
}
```

## Commands

```bash
# Service management
systemctl --user start wayvoxtral
systemctl --user stop wayvoxtral
systemctl --user status wayvoxtral

# View logs
journalctl --user -u wayvoxtral -f
```

## How It Works

```
[F9] → daemon (evdev listener)
             ↓
      [Recording via PyAudio]
             ↓
[F9] → daemon → [Mistral API transcription]
             ↓
      [ydotool injects text into active window]
```

## Troubleshooting

### "No input devices found"
```bash
sudo usermod -aG input $USER
# Log out and back in
```

### "ydotool not found"
```bash
sudo apt install ydotool
sudo systemctl enable --now ydotoold
```

### "API key not configured"
Edit `~/.config/wayvoxtral/config.json` and add your Mistral API key.

## License

Apache 2.0
