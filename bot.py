import asyncio
import os
import logging
from telegram import Bot
from telegram.error import TelegramError
from utils.scraper import AznudeScraper
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, BASE_URL, START_PAGE
import requests
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATE_FILE = 'last_sent.txt'

def get_last_sent():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    return None

def set_last_sent(url):
    with open(STATE_FILE, 'w') as f:
        f.write(url)

async def send_video(bot, chat_id, video_url, title, page_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(video_url, stream=True, timeout=60, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to download video: {video_url} (status: {response.status_code})")
            return False

        filename = f"temp_{int(time.time())}.mp4"
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        caption = f"🎬 {title}\n🔗 {page_url}"
        with open(filename, 'rb') as f:
            await bot.send_video(
                chat_id=chat_id,
                video=f,
                caption=caption,
                supports_streaming=True
            )

        os.remove(filename)
        logger.info(f"Sent video: {title}")
        return True

    except Exception as e:
        logger.error(f"Error sending video: {e}")
        return False

async def main():
    logger.info("Starting aznude bot...")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    scraper = AznudeScraper(headless=True)

    # Get recent videos
    videos = scraper.get_new_videos(START_PAGE)
    
    if not videos:
        logger.info("No videos found - check selectors or site structure")
        return

    last_sent = get_last_sent()
    new_videos = []

    for video in videos:
        if video['url'] == last_sent:
            break
        new_videos.append(video)

    new_videos.reverse()

    if not new_videos:
        logger.info("No new videos since last run")
        return

    logger.info(f"Sending {len(new_videos)} new videos")

    for video in new_videos:
        video_url = scraper.extract_video_url(video['url'])
        if not video_url:
            logger.warning(f"Could not extract video from {video['url']}")
            continue

        success = await send_video(
            bot,
            TELEGRAM_CHAT_ID,
            video_url,
            video['title'],
            video['url']
        )

        if success:
            set_last_sent(video['url'])

        await asyncio.sleep(1)

    logger.info("Done!")

if __name__ == "__main__":
    asyncio.run(main())
