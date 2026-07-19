import os
import json
import time
import requests
import yt_dlp
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

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

def get_cookies_from_page(page_url):
    """دریافت کوکی‌های معتبر با استفاده از Selenium"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")
    
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get(page_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)
        
        # دریافت کوکی‌ها
        cookies = driver.get_cookies()
        driver.quit()
        
        # تبدیل به فرمت مناسب برای yt-dlp
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        return cookie_string
        
    except Exception as e:
        print(f"  ❌ خطا در دریافت کوکی: {e}")
        driver.quit()
        return None

def get_direct_video_url_with_ytdlp(page_url):
    """استخراج لینک مستقیم ویدیو با استفاده از yt-dlp و کوکی"""
    print(f"  📄 استخراج ویدیو از: {page_url}")
    
    # اول کوکی بگیر
    cookies = get_cookies_from_page(page_url)
    if not cookies:
        print("  ⚠️ کوکی دریافت نشد")
        return None
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': True,
            'cookiefile': None,  # استفاده از کوکی مستقیم
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
                'Cookie': cookies
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(page_url, download=False)
            if info and 'url' in info:
                video_url = info['url']
                print(f"  ✅ ویدیو اصلی پیدا شد: {video_url}")
                return video_url
            elif info and 'formats' in info and len(info['formats']) > 0:
                best_format = max(info['formats'], key=lambda f: f.get('height', 0) or 0)
                video_url = best_format.get('url')
                if video_url:
                    print(f"  ✅ ویدیو اصلی پیدا شد: {video_url}")
                    return video_url
        
        print(f"  ⚠️ ویدیویی با yt-dlp پیدا نشد")
        return None
        
    except Exception as e:
        print(f"  ❌ خطا در yt-dlp: {e}")
        return None

def get_new_posts():
    """دریافت لینک مطالب جدید از صفحه مشخص"""
    print(f"🔍 اسکرپینگ از: {TARGET_URL}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")
    
    try:
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.get(TARGET_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)
        
        new_posts = []
        
        links = driver.find_elements(By.XPATH, "//a[contains(@href, '/view/celeb/') or contains(@href, '/view/movie/')]")
        
        for link in links[:15]:
            try:
                href = link.get_attribute('href')
                title = link.text.strip() or "مطلب جدید"
                if href and not any(p['link'] == href for p in new_posts):
                    new_posts.append({
                        'title': title,
                        'link': href
                    })
            except:
                pass
        
        driver.quit()
        
        print(f"  ✅ {len(new_posts)} مطلب پیدا شد.")
        return new_posts[:10]
        
    except Exception as e:
        print(f"  ❌ خطا: {e}")
        return []

def send_video_to_telegram(post, video_url):
    """ارسال ویدیو به تلگرام"""
    caption = f"{post['title']}\n{post['link']}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(video_url, headers=headers, timeout=60)
        if response.status_code != 200:
            return False
        
        file_name = f"{post['title']}.mp4"
        files = {'video': (file_name, response.content, 'video/mp4')}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        
        result = requests.post(f"{TELEGRAM_API_URL}/sendVideo", data=data, files=files, timeout=60)
        if result.ok:
            return True
        else:
            print(f"  ⚠️ خطا: {result.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ خطا: {e}")
        return False

def send_to_telegram(post):
    """ارسال مطلب با ویدیو"""
    print(f"  📤 ارسال: {post['title']}")
    
    video_url = get_direct_video_url_with_ytdlp(post['link'])
    
    if video_url:
        if send_video_to_telegram(post, video_url):
            print(f"  ✅ ویدیو ارسال شد")
            return
    
    try:
        caption = f"{post['title']}\n{post['link']}"
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': caption}
        )
        print(f"  📝 متن ارسال شد")
    except Exception as e:
        print(f"  ❌ خطا: {e}")

def main():
    print("🚀 شروع...")
    sent_links = load_sent_links()
    print(f"  📋 {len(sent_links)} لینک قبلا ارسال شده")
    
    all_posts = get_new_posts()
    
    if not all_posts:
        print("❌ هیچ مطلبی پیدا نشد")
        return

    posts_to_send = [p for p in all_posts if p['link'] not in sent_links]
    print(f"  📨 {len(posts_to_send)} مطلب جدید")

    if not posts_to_send:
        print("✅ همه قبلا ارسال شدن")
        return

    for post in posts_to_send[:10]:
        send_to_telegram(post)
        sent_links.add(post['link'])
        time.sleep(3)

    save_sent_links(sent_links)
    print("✅ پایان")

if __name__ == "__main__":
    main()
