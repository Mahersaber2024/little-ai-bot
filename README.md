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
2. Copy or clone the project files and install Python packages into a
   virtual environment.
3. Set up the PostgreSQL database and a dedicated database user.
4. Ask for the bot token (only if one isn't already configured) and the
   owner admin ID(s).
5. Save everything — database credentials, bot token, owner admin
   ID(s) — into `config/bot_settings.json`. There is no `.env` file
   anywhere in this project.
6. Create and start the `littleai-bot` systemd service.

Spotify API credentials are **not** requested during install. Set them
after the bot is running, from inside Telegram: `/admin` → 🎵 **Spotify
Settings**.

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

Project files, `config/bot_settings.json`, and the Python virtual
environment are stored in this directory.

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

On first run, if no bot token is configured yet, you'll be prompted for
it interactively; it's then saved to `config/bot_settings.json` and
won't be asked again. Spotify credentials, admin IDs (beyond `.env`'s
`ADMIN_USER_IDS`), and everything else are configured from `/admin`
once the bot is running.

## Configuration

There is no `.env` file anywhere in this project. Every setting the bot
needs — database credentials, owner admin ID(s), the bot token, Spotify
API credentials, bot name, sponsor channels, forced membership,
logging, other admins — lives in a single file:
`config/bot_settings.json` (created with `chmod 600`).

- Database credentials, the bot token, and owner admin ID(s) are seeded
  once by `install.sh`. Re-running the installer on an existing install
  keeps the current bot token and shows the current owner admin ID(s)
  as the default, instead of wiping them out.
- Spotify credentials, and everything else changeable from inside
  Telegram, can be set or changed any time from `/admin`, with no
  restart required.

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

Admins additionally get an inline admin panel reachable from inside the
bot: ban/unban users, manage sponsor channels, manage other admins,
configure logging, and set the Spotify API credentials (Client ID,
Client Secret, Redirect URI).

## License

MIT License. See [`LICENSE`](LICENSE) for the full license text.
