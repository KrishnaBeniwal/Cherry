# Cherry Bot

A Discord bot that provides tracking, reminders, and utilities for the Dank Memer Discord bot.

## Features

### Automated Reminders
- **Activity Tracking:** Provides reminders for fishing, farming, streaming, pets, items, prestige, adventures, and work shifts.
- **Dank Memer Integration:** Parses embeds and messages from Dank Memer to trigger and cancel reminders based on user activity.
- **Custom Reminders:** Allows users to set custom personal reminders.

### Utilities and UI
- **Market Assistant:** Includes tools to assist with tracking and evaluating items in the Dank Memer market.
- **Interactive Interface:** Uses Discord buttons and dropdown menus for managing personal settings and snoozing active reminders.

## Technologies Used
- Python
- discord.py
- aiosqlite
- python-dotenv

## Project Structure
- `cogs/` - Modular feature extensions for reminders, settings, and other bot commands.
- `core/` - Core utilities including database management, task scheduling, and fuzzy matching.
- `main.py` - Main entry point and bot setup logic.
- `dank_data.py` - Static lookup data for items and fish.
- `emojis.py` - Custom emoji definitions used by the bot.
- `requirements.txt` - Python dependencies required to run the bot.
- `.env.example` - Template for environment variables.
- `.gitignore` - Git ignore rules to prevent committing sensitive or temporary files.

## Requirements
- Python 3.9+
- A registered Discord Bot Token

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file based on the example and add your bot token:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to include your token:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

*(Note: The SQLite database, `reminders.db`, is automatically initialized on the first run.)*


## License

This project is intended for personal and educational use.
