import os
import json
import time
import logging
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("لطفاً TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID را در Secrets تنظیم کنید.")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SENT_FILE = "sent_links.json"
LIST_PAGE_URL = "https://www.aznude.com/browse/videos/recent/1.html"

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

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def get_video_links_from_list_page():
    logger.info(f"🔍 اسکرپینگ صفحه لیست: {LIST_PAGE_URL}")
    driver = init_driver()
    video_links = []
    
    try:
        driver.get(LIST_PAGE_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)
        
        all_links = driver.find_elements(By.TAG_NAME, "a")
        
        for link in all_links:
            try:
                href = link.get_attribute('href')
                if href and '/azncdn/' in href:
                    # عنوان رو از تگ img بگیر
                    title = None
                    try:
                        img = link.find_element(By.TAG_NAME, "img")
                        title = img.get_attribute('alt')
                    except:
                        pass
                    
                    if not title:
                        title = link.text.strip() or "ویدیو جدید"
                    
                    video_links.append({
                        'title': title,
                        'link': href
                    })
                    logger.info(f"  ✅ ویدیو پیدا شد: {title[:30]}...")
            except:
                continue
        
        logger.info(f"✅ {len(video_links)} ویدیو در صفحه لیست پیدا شد.")
        return video_links[:10]
        
    except Exception as e:
        logger.error(f"❌ خطا: {e}")
        return []
    finally:
        driver.quit()

def extract_video_title(driver):
    """گرفتن عنوان کامل از تگ h1 صفحه ویدیو"""
    try:
        # روش 1: از تگ h1 با کلاس single-video-title
        h1 = driver.find_element(By.CSS_SELECTOR, "h1.single-video-title")
        full_title = h1.text.strip()
        if full_title:
            return full_title
    except:
        pass
    
    try:
        # روش 2: از تگ title
        title = driver.title
        if title:
            return title
    except:
        pass
    
    return None

def extract_video_url_from_page(page_url):
    """
    استخراج لینک مستقیم ویدیو و عنوان از صفحه ویدیو
    """
    logger.info(f"📄 استخراج ویدیو از: {page_url}")
    driver = init_driver()
    
    try:
        driver.get(page_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        
        # گرفتن عنوان از صفحه
        video_title = extract_video_title(driver)
        if video_title:
            logger.info(f"  📌 عنوان: {video_title[:50]}...")
        else:
            logger.info(f"  📌 عنوانی پیدا نشد، از عنوان قبلی استفاده می‌شود.")
        
        # پیدا کردن دکمه دانلود (تگ a که به mp4 ختم میشه)
        try:
            download_link = driver.find_element(By.CSS_SELECTOR, "a[href$='.mp4']")
            video_url = download_link.get_attribute('href')
            if video_url and video_url.startswith('http') and '.mp4' in video_url:
                logger.info(f"✅ لینک دانلود پیدا شد: {video_url[:60]}...")
                driver.quit()
                return video_url, video_title
        except:
            pass
        
        # اگر دکمه دانلود پیدا نشد، از روش قبلی (تگ video) استفاده کن
        try:
            video = driver.find_element(By.TAG_NAME, "video")
            video_url = video.get_attribute('src')
            if video_url and video_url.startswith('http'):
                logger.info(f"✅ ویدیو از تگ video پیدا شد: {video_url[:60]}...")
                driver.quit()
                return video_url, video_title
        except:
            pass
        
        logger.warning(f"⚠️ ویدیو در {page_url} پیدا نشد")
        driver.quit()
        return None, None
        
    except Exception as e:
        logger.error(f"❌ خطا: {e}")
        driver.quit()
        return None, None

def send_video_to_telegram(post, video_url):
    caption = f"{post['title']}\n{post['link']}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(video_url, headers=headers, timeout=60)
        if response.status_code != 200:
            logger.warning(f"دانلود ویدیو ناموفق: {response.status_code}")
            return False
        
        # نام فایل رو از عنوان میگیریم
        safe_title = post['title'].replace('/', '_').replace('\\', '_')[:50]
        file_name = f"{safe_title}.mp4"
        
        files = {'video': (file_name, response.content, 'video/mp4')}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        
        result = requests.post(f"{TELEGRAM_API_URL}/sendVideo", data=data, files=files, timeout=60)
        if result.ok:
            logger.info(f"✅ ویدیو ارسال شد: {post['title'][:30]}...")
            return True
        else:
            logger.warning(f"خطای تلگرام: {result.text}")
            return False
    except Exception as e:
        logger.error(f"خطا در ارسال ویدیو: {e}")
        return False

def send_text_to_telegram(post):
    caption = f"{post['title']}\n{post['link']}"
    try:
        result = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': caption}
        )
        if result.ok:
            logger.info(f"📝 متن ارسال شد: {post['title'][:30]}...")
            return True
    except Exception as e:
        logger.error(f"خطا در ارسال متن: {e}")
    return False

def main():
    logger.info("🚀 شروع ربات...")
    sent_links = load_sent_links()
    logger.info(f"📋 {len(sent_links)} لینک قبلا ارسال شده")
    
    all_posts = get_video_links_from_list_page()
    if not all_posts:
        logger.info("❌ هیچ ویدیویی پیدا نشد")
        return
    
    posts_to_send = [p for p in all_posts if p['link'] not in sent_links]
    logger.info(f"📨 {len(posts_to_send)} ویدیو جدید برای ارسال")
    
    if not posts_to_send:
        logger.info("✅ همه ویدیوها قبلا ارسال شده‌اند")
        return
    
    for post in posts_to_send:
        logger.info(f"📤 پردازش: {post['title'][:30]}...")
        
        video_url, video_title = extract_video_url_from_page(post['link'])
        
        if video_url:
            # اگر عنوان جدید پیدا شد، جایگزین کن
            if video_title:
                post['title'] = video_title
                logger.info(f"  🏷️ عنوان به‌روز شد: {post['title'][:50]}...")
            
            if send_video_to_telegram(post, video_url):
                sent_links.add(post['link'])
        else:
            logger.warning(f"⚠️ ویدیو برای {post['title'][:30]}... پیدا نشد")
            if send_text_to_telegram(post):
                sent_links.add(post['link'])
        
        time.sleep(3)
    
    save_sent_links(sent_links)
    logger.info("✅ پایان کار")

if __name__ == "__main__":
    main()
