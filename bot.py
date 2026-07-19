import os
import json
import time
import requests
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

# 🔴 صفحه مشخصی که ربات فقط از اونجا میگیره
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

def get_media_from_page(page_url):
    """دریافت اولین ویدیو یا عکس از صفحه مطلب"""
    print(f"  📄 دریافت محتوا از: {page_url}")
    
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
        time.sleep(3)
        
        # اولویت با ویدیو
        try:
            video = driver.find_element(By.XPATH, "//video/source | //video")
            src = video.get_attribute('src')
            if src and src.startswith('http'):
                driver.quit()
                return src, 'video'
        except:
            pass
        
        # بعد عکس
        try:
            img = driver.find_element(By.XPATH, "//div[contains(@class, 'video-container')]//img | //div[contains(@class, 'photo')]//img | //img[contains(@src, 'cdn.aznude.com')]")
            src = img.get_attribute('src')
            if src and src.startswith('http'):
                if 'thumb' in src:
                    src = src.replace('thumb', 'large')
                driver.quit()
                return src, 'image'
        except:
            pass
        
        driver.quit()
        return None, None
        
    except Exception as e:
        print(f"  ❌ خطا: {e}")
        driver.quit()
        return None, None

def get_new_posts():
    """دریافت مطالب جدید فقط از صفحه مشخص شده"""
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
        
        # فقط لینک‌هایی که به /view/celeb/ یا /view/movie/ ختم میشن
        links = driver.find_elements(By.XPATH, "//a[contains(@href, '/view/celeb/') or contains(@href, '/view/movie/')]")
        
        for link in links[:15]:
            try:
                href = link.get_attribute('href')
                title = link.text.strip() or "مطلب جدید"
                if href:
                    new_posts.append({
                        'title': title,
                        'link': href
                    })
            except:
                pass
        
        driver.quit()
        
        # حذف تکراری
        unique_posts = []
        seen = set()
        for post in new_posts:
            if post['link'] not in seen:
                seen.add(post['link'])
                unique_posts.append(post)
        
        print(f"  ✅ {len(unique_posts)} مطلب پیدا شد.")
        return unique_posts[:10]
        
    except Exception as e:
        print(f"  ❌ خطا: {e}")
        return []

def send_media_to_telegram(post, media_url, media_type):
    """ارسال فایل به تلگرام"""
    caption = f"{post['title']}\n{post['link']}"
    
    try:
        response = requests.get(media_url, timeout=30)
        if response.status_code != 200:
            return False
        
        content = response.content
        ext = 'mp4' if media_type == 'video' else 'jpg'
        file_name = f"{post['title']}.{ext}"
        
        if media_type == 'video':
            send_url = f"{TELEGRAM_API_URL}/sendVideo"
        else:
            send_url = f"{TELEGRAM_API_URL}/sendPhoto"
        
        files = {media_type: (file_name, content)}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        
        result = requests.post(send_url, data=data, files=files, timeout=60)
        return result.ok
            
    except Exception as e:
        print(f"  ❌ خطا: {e}")
        return False

def send_to_telegram(post):
    """ارسال مطلب"""
    print(f"  📤 ارسال: {post['title']}")
    
    media_url, media_type = get_media_from_page(post['link'])
    
    if media_url:
        if send_media_to_telegram(post, media_url, media_type):
            print(f"  ✅ ارسال شد")
            return
    
    # در صورت شکست، فقط متن
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
