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

# صفحه مشخصی که ربات فقط از اونجا میگیره
TARGET_URL = "https://www.aznude.com/browse/videos/recent/1.html"

def load_sent_links():
    try:
        with open(SENT_FILE, 'r') as f:
            return set(json.load(f))
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

def send_to_telegram(post):
    """ارسال مطلب با لینک به عنوان ویدیو یا عکس"""
    print(f"  📤 ارسال: {post['title']}")
    
    # تلاش برای ارسال به عنوان ویدیو
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendVideo",
            data={
                'chat_id': CHAT_ID,
                'video': post['link'],
                'caption': post['title']
            },
            timeout=30
        )
        if response.ok:
            print(f"  ✅ ویدیو ارسال شد: {post['link']}")
            return
        else:
            print(f"  ⚠️ ارسال ویدیو失敗: {response.text}")
    except Exception as e:
        print(f"  ❌ خطا در ارسال ویدیو: {e}")
    
    # اگر ویدیو نشد، تلاش برای ارسال به عنوان عکس
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendPhoto",
            data={
                'chat_id': CHAT_ID,
                'photo': post['link'],
                'caption': post['title']
            },
            timeout=30
        )
        if response.ok:
            print(f"  ✅ عکس ارسال شد: {post['link']}")
            return
        else:
            print(f"  ⚠️ ارسال عکس失敗: {response.text}")
    except Exception as e:
        print(f"  ❌ خطا در ارسال عکس: {e}")
    
    # در صورت شکست، به عنوان متن ارسال کن
    try:
        caption = f"{post['title']}\n{post['link']}"
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': caption},
            timeout=30
        )
        if response.ok:
            print(f"  📝 متن ارسال شد")
        else:
            print(f"  ❌ خطا در ارسال متن: {response.text}")
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
            time.sleep(3)  # تاخیر ۳ ثانیه‌ای
        except Exception as e:
            print(f"  ❌ خطا در ارسال: {e}")

    save_sent_links(sent_links)
    print("\n✅ پایان کار.")

if __name__ == "__main__":
    main()
