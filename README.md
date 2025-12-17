# dyson-cli

A command-line interface for controlling Dyson air purifiers, fans, and heaters.

## Features

- 🔌 **Local control** - Communicates directly with your Dyson device over MQTT (no cloud required after setup)
- 🌡️ **Full control** - Power, fan speed, oscillation, heat mode, target temperature
- 📊 **Status monitoring** - View current state, air quality, and environmental data
- 🔐 **Easy setup** - Fetch credentials automatically via your Dyson account

## Supported Devices

- Dyson Pure Cool Link (TP02, DP01)
- Dyson Pure Cool (TP04, DP04)
- Dyson Pure Hot+Cool Link (HP02)
- Dyson Pure Hot+Cool (HP04, HP06, HP07, HP09)
- Dyson Pure Humidify+Cool (PH01, PH03, PH04)
- Dyson Purifier Big+Quiet (BP02, BP03, BP04)

## Installation

```bash
pip install dyson-cli
```

Or install from source:

```bash
git clone https://github.com/tmustier/dyson-cli.git
cd dyson-cli
pip install -e .
```

## Quick Start

### 1. Setup (one-time)

Fetch your device credentials via your Dyson account:

```bash
dyson setup
```

This will:
1. Send an OTP to your Dyson account email
2. Fetch your device credentials
3. Save them to `~/.dyson/config.json`

### 2. List devices

```bash
dyson list
```

### 3. Control your device

```bash
# Power
dyson on
dyson off

# Fan
dyson fan speed 5        # Set speed (1-10 or "auto")
dyson fan oscillate on   # Enable oscillation

# Heat (Hot+Cool models only)
dyson heat on
dyson heat target 22     # Set target temperature (°C)

# Status
dyson status             # Show current state
dyson status --json      # JSON output for scripting
```

## Commands

| Command | Description |
|---------|-------------|
| `dyson setup` | Configure device credentials |
| `dyson list` | List configured devices |
| `dyson status` | Show device status |
| `dyson on` | Turn device on |
| `dyson off` | Turn device off |
| `dyson fan speed <1-10\|auto>` | Set fan speed |
| `dyson fan oscillate <on\|off>` | Control oscillation |
| `dyson heat on\|off` | Control heat mode |
| `dyson heat target <temp>` | Set target temperature |
| `dyson night <on\|off>` | Control night mode |

## Configuration

Credentials are stored in `~/.dyson/config.json`:

```json
{
  "devices": [
    {
      "name": "Living Room",
      "serial": "XXX-XX-XXXXXXXX",
      "credential": "...",
      "product_type": "527",
      "ip": "192.168.1.100"
    }
  ],
  "default_device": "Living Room"
}
```

## How It Works

Dyson devices communicate locally via MQTT on port 1883. After initial setup (which requires your Dyson account), all control happens directly on your local network - no cloud required.

## Credits

Built on top of [libdyson](https://github.com/shenxn/libdyson), the Python library that powers the Home Assistant Dyson integration.

## License

MIT
