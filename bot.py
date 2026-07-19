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

# --- تنظیمات برگرفته از Secrets گیت‌هاب ---
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("لطفاً TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID را در Secrets تنظیم کنید.")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SITE_URL = "https://aznude.com"
SENT_FILE = "sent_links.json"

def load_sent_links():
    try:
        with open(SENT_FILE, 'r') as f:
            data = json.load(f)
            return set(data)
    except FileNotFoundError:
        print("  ℹ️ فایل sent_links.json پیدا نشد، یک مجموعه خالی ایجاد می‌شود.")
        return set()
    except json.JSONDecodeError:
        print("  ⚠️ فایل sent_links.json خراب است، یک مجموعه خالی ایجاد می‌شود.")
        return set()

def save_sent_links(links):
    try:
        with open(SENT_FILE, 'w') as f:
            json.dump(list(links), f)
        print(f"  💾 {len(links)} لینک در فایل sent_links.json ذخیره شد.")
    except Exception as e:
        print(f"  ❌ خطا در ذخیره فایل: {e}")

def get_media_from_page(page_url):
    """دریافت اولین فایل (ویدیو یا عکس) از صفحه یک مطلب"""
    print(f"  📄 در حال بررسی صفحه: {page_url}")
    
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
        
        # 1. جستجوی ویدیو
        try:
            video_source = driver.find_element(By.XPATH, "//video/source | //video")
            if video_source:
                media_url = video_source.get_attribute('src')
                if media_url and media_url.startswith('http'):
                    driver.quit()
                    return media_url, 'video'
        except:
            pass
        
        # 2. جستجوی عکس
        try:
            img = driver.find_element(By.XPATH, "//div[contains(@class, 'video-container')]//img | //div[contains(@class, 'photo')]//img | //img[contains(@src, 'cdn.aznude.com')]")
            if img:
                img_url = img.get_attribute('src')
                if img_url and img_url.startswith('http'):
                    if 'thumb' in img_url:
                        img_url = img_url.replace('thumb', 'large').replace('_t.', '.')
                    driver.quit()
                    return img_url, 'image'
        except:
            pass
        
        driver.quit()
        return None, None
        
    except Exception as e:
        print(f"  ❌ خطا در دریافت محتوا از {page_url}: {e}")
        driver.quit()
        return None, None

def get_new_posts():
    """دریافت لینک مطالب جدید از صفحه اصلی"""
    print("🔍 شروع اسکرپینگ صفحه اصلی...")
    
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
        
        driver.get(SITE_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)
        
        new_posts = []
        
        # پیدا کردن بخش "Videos Added on"
        try:
            sections = driver.find_elements(By.XPATH, "//*[contains(text(), 'Videos Added on')]")
            if sections:
                parent = sections[0].find_element(By.XPATH, "..")
                links = parent.find_elements(By.TAG_NAME, "a")
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and ('/view/celeb/' in href or '/view/movie/' in href):
                            title = link.text.strip() or "مطلب جدید"
                            new_posts.append({
                                'title': title,
                                'link': href
                            })
                    except Exception as e:
                        print(f"  ⚠️ خطا در پردازش لینک: {e}")
            else:
                print("  ⚠️ بخش 'Videos Added on' پیدا نشد.")
        except Exception as e:
            print(f"  ❌ خطا در پیدا کردن مطالب: {e}")
        
        # اگر روش اول موفق نشد، روش دوم را امتحان کن
        if not new_posts:
            print("  🔄 تلاش با روش دوم (جستجوی مستقیم)...")
            try:
                # پیدا کردن تمام لینک‌های مطالب
                all_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/view/celeb/') or contains(@href, '/view/movie/')]")
                for link in all_links[:15]:
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
            except Exception as e:
                print(f"  ❌ خطا در روش دوم: {e}")
        
        driver.quit()
        
        # حذف تکراری‌ها
        unique_posts = []
        seen = set()
        for post in new_posts:
            if post['link'] not in seen:
                seen.add(post['link'])
                unique_posts.append(post)
        
        print(f"  ✅ {len(unique_posts)} مطلب جدید پیدا شد.")
        return unique_posts[:10]
        
    except Exception as e:
        print(f"  ❌ خطا در راه‌اندازی مرورگر: {e}")
        return []

def send_media_to_telegram(post, media_url, media_type):
    """ارسال فایل (عکس یا ویدیو) به تلگرام"""
    caption = f"{post['title']}\n{post['link']}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(media_url, headers=headers, timeout=30)
        if response.status_code != 200:
            return False
        
        file_content = response.content
        file_name = f"{post['title']}.{media_type == 'video' and 'mp4' or 'jpg'}"
        
        if media_type == 'video':
            send_url = f"{TELEGRAM_API_URL}/sendVideo"
        else:
            send_url = f"{TELEGRAM_API_URL}/sendPhoto"
        
        files = {
            media_type: (file_name, file_content)
        }
        data = {'chat_id': CHAT_ID, 'caption': caption}
        
        result = requests.post(send_url, data=data, files=files, timeout=60)
        if result.ok:
            return True
        else:
            print(f"  ⚠️ خطا در ارسال به تلگرام: {result.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ خطا در دانلود یا ارسال: {e}")
        return False

def send_to_telegram(post):
    """ارسال مطلب با فایل (عکس یا ویدیو) به تلگرام"""
    print(f"  📤 در حال ارسال: {post['title']}")
    
    media_url, media_type = get_media_from_page(post['link'])
    
    if media_url:
        success = send_media_to_telegram(post, media_url, media_type)
        if success:
            print(f"  ✅ ارسال {media_type} برای {post['title']} موفق بود.")
            return
        else:
            print(f"  ⚠️ ارسال فایل برای {post['title']} ناموفق بود.")
    
    # در صورت شکست، فقط متن ارسال می‌شود
    try:
        caption = f"{post['title']}\n{post['link']}"
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': caption}
        )
        print(f"  📝 ارسال متن برای {post['title']} انجام شد.")
    except Exception as e:
        print(f"  ❌ خطا در ارسال متن: {e}")

def main():
    print("🚀 شروع اسکرپینگ...")
    sent_links = load_sent_links()
    print(f"  📋 {len(sent_links)} لینک قبلاً ارسال شده است.")
    
    all_posts = get_new_posts()
    
    if not all_posts:
        print("❌ هیچ مطلبی پیدا نشد.")
        return

    posts_to_send = [p for p in all_posts if p['link'] not in sent_links]
    print(f"  📨 {len(posts_to_send)} مطلب جدید برای ارسال پیدا شد.")
    
    if not posts_to_send:
        print("✅ همه مطالب قبلاً ارسال شده‌اند.")
        return

    for i, post in enumerate(posts_to_send[:10]):
        print(f"\n--- ارسال {i+1} از {len(posts_to_send[:10])} ---")
        try:
            send_to_telegram(post)
            sent_links.add(post['link'])
            time.sleep(5)
        except Exception as e:
            print(f"  ❌ خطا در ارسال: {e}")

    save_sent_links(sent_links)
    print("\n✅ پایان کار.")

if __name__ == "__main__":
    main()
