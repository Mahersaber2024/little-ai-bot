# Little AI – Telegram Spotify Bot

A Telegram bot that lets a group control a shared Spotify account: search
tracks, albums and artists, manage playlists, control playback, get
recommendations, and moderate the chat with a small admin panel.

## Quick Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Mahersaber2024/little-ai-bot/main/install.sh)
```

The installer installs the bot in `/opt/littleai_bot` by default. It will:

1. Install system dependencies such as Python and PostgreSQL.
2. Set up the PostgreSQL database and a dedicated database user.
3. Ask for the bot token, owner admin ID(s), and Spotify API credentials.
4. Copy or clone the project files and install Python packages into a
   virtual environment.
5. Write the `.env` file with all collected settings.
6. Create and start the `littleai-bot` systemd service.

After installation, verify that the service is running:

```bash
systemctl status littleai-bot
```

## Uninstall

```bash
sudo bash uninstall.sh
```

The uninstaller will:

1. Stop and remove the `littleai-bot` systemd service.
2. Optionally drop the PostgreSQL database and user (asked interactively).
3. Optionally delete the project files and `.env` from the install
   directory (asked interactively).

You can run it from anywhere — it looks up the install directory
automatically, or lets you enter it manually.

## Installation Path

The default installation path is:

```text
/opt/littleai_bot
```

Project files, the `.env` file, and the Python virtual environment are
stored in this directory.

## Manual Installation

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip postgresql

git clone https://github.com/Mahersaber2024/little-ai-bot.git
cd little-ai-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 little_ai.py
```

## Configuration

All secrets (bot token, admin IDs, database credentials, Spotify API
credentials) live in `.env` and are written by the installer. Settings
that admins can change from inside Telegram — bot name, sponsor
channels, forced membership, logging — are stored separately in
`config/bot_settings.json` so they persist across restarts without
touching `.env`.

## Service Management

```bash
systemctl start littleai-bot
systemctl stop littleai-bot
systemctl restart littleai-bot
systemctl status littleai-bot
```

View logs:

```bash
journalctl -u littleai-bot -f
```

## Bot Commands

- `/start` – Welcome message.
- `/help` – Show help.
- `/account` – Log in and manage the linked Spotify account (profile,
  playlists, liked tracks, playback control).
- `/music` – Open the search menu (tracks, albums, artists).
- `/recommend [genre]` – Get track recommendations for a genre.
- `/category_playlists [id]` – Show playlists in a Spotify category.

Admins additionally get an inline admin panel (ban/unban users, manage
sponsor channels, manage other admins, configure logging) reachable from
inside the bot.

## License

MIT License. See [`LICENSE`](LICENSE) for the full license text.
