# aznude-telegram-bot

Automated Telegram bot that scrapes latest videos from aznude.com and sends them to your Telegram.

## Setup

1. Clone the repo
2. Add your Telegram bot token and chat ID as GitHub secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. The workflow runs every 3 hours automatically

## Local Testing

```bash
pip install -r requirements.txt
python bot.py
