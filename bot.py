import os
import json
import time
import logging
import requests
from utils.scraper import AznudeScraper

# --- تنظیمات لاگ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- تنظیمات ---
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("لطفاً TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID را در Secrets تنظیم کنید.")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SENT_FILE = "sent_links.json"
TARGET_URL = "https://www.aznude.com/browse/videos/recent/1.html"

def load_sent_links():
    try:
        with open(SENT_FILE, 'r') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()
    except json.JSONDecodeError:
        return set()

def save_sent_links(links):
    with open(SENT_FILE, 'w') as f:
        json.dump(list(links), f)

def send_video_to_telegram(post, video_url):
    """ارسال ویدیو به تلگرام"""
    caption = f"{post['title']}\n{post['link']}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(video_url, headers=headers, timeout=60)
        if response.status_code != 200:
            logger.warning(f"Failed to download video: {response.status_code}")
            return False
        
        file_name = f"{post['title']}.mp4"
        files = {'video': (file_name, response.content, 'video/mp4')}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        
        result = requests.post(f"{TELEGRAM_API_URL}/sendVideo", data=data, files=files, timeout=60)
        if result.ok:
            logger.info(f"✅ Sent video: {post['title']}")
            return True
        else:
            logger.warning(f"Telegram error: {result.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        return False

def send_text_to_telegram(post):
    """ارسال متن به تلگرام (در صورت عدم موفقیت در یافتن ویدیو)"""
    caption = f"{post['title']}\n{post['link']}"
    try:
        result = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': caption}
        )
        if result.ok:
            logger.info(f"📝 Sent text for: {post['title']}")
            return True
        else:
            logger.warning(f"Telegram error: {result.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending text: {e}")
        return False

def main():
    logger.info("🚀 Starting bot...")
    
    sent_links = load_sent_links()
    logger.info(f"📋 {len(sent_links)} links already sent")
    
    scraper = AznudeScraper()
    
    # مرحله ۱: دریافت لینک‌های جدید از صفحه لیست
    all_posts = scraper.get_list_page_links(TARGET_URL)
    
    if not all_posts:
        logger.info("❌ No new posts found")
        return

    # فیلتر کردن لینک‌های قبلاً ارسال شده
    posts_to_send = [p for p in all_posts if p['link'] not in sent_links]
    logger.info(f"📨 {len(posts_to_send)} new videos to send")

    if not posts_to_send:
        logger.info("✅ All videos already sent")
        return

    # مرحله ۲: برای هر لینک، ویدیو را استخراج و ارسال کن
    for post in posts_to_send[:10]:
        logger.info(f"📤 Processing: {post['title']}")
        
        # استخراج ویدیو با CDP
        video_url = scraper.extract_main_video_with_cdp(post['link'])
        
        if video_url:
            if send_video_to_telegram(post, video_url):
                sent_links.add(post['link'])
        else:
            # اگر ویدیو پیدا نشد، فقط متن ارسال کن
            logger.warning(f"⚠️ Could not extract video from {post['link']}")
            if send_text_to_telegram(post):
                sent_links.add(post['link'])
        
        time.sleep(3)  # تاخیر بین هر درخواست

    save_sent_links(sent_links)
    logger.info("✅ Done!")

if __name__ == "__main__":
    main()
