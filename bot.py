import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
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
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent_links(links):
    with open(SENT_FILE, 'w') as f:
        json.dump(list(links), f)

def get_new_posts():
    """استفاده از selenium برای بارگذاری کامل صفحه و استخراج محتوا"""
    print("راه‌اندازی مرورگر...")
    
    # تنظیمات مرورگر بدون رابط کاربری (headless)
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # اجرا بدون نمایش مرورگر
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # راه‌اندازی مرورگر
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"بارگذاری صفحه {SITE_URL}...")
        driver.get(SITE_URL)
        
        # منتظر بارگذاری محتوای اصلی
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # صبر بیشتر برای بارگذاری کامل محتوا (مخصوصاً محتوای داینامیک)
        time.sleep(5)
        
        # پیدا کردن بخش ویدیوهای جدید
        new_posts = []
        
        # روش 1: پیدا کردن بخش "Videos Added on"
        try:
            # پیدا کردن هدر بخش
            sections = driver.find_elements(By.XPATH, "//*[contains(text(), 'Videos Added on')]")
            if sections:
                parent = sections[0].find_element(By.XPATH, "..")
                # پیدا کردن آیتم‌های ویدیو
                video_items = parent.find_elements(By.XPATH, ".//a[contains(@href, '/video/') or contains(@href, '/watch/')]")
                
                for item in video_items[:15]:
                    try:
                        link = item.get_attribute('href')
                        title = item.text.strip() or "ویدیو جدید"
                        
                        # پیدا کردن تصویر نزدیک
                        img = item.find_element(By.XPATH, ".//img | ../img")
                        img_url = img.get_attribute('src') if img else None
                        
                        new_posts.append({
                            'title': title,
                            'link': link,
                            'image': img_url
                        })
                    except Exception as e:
                        print(f"خطا در استخراج یک آیتم: {e}")
        except Exception as e:
            print(f"خطا در روش 1: {e}")
        
        # روش 2: اگر روش اول موفق نشد، تمام لینک‌های ویدیو را پیدا کن
        if not new_posts:
            try:
                all_video_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/video/') or contains(@href, '/watch/')]")
                for link in all_video_links[:15]:
                    try:
                        url = link.get_attribute('href')
                        title = link.text.strip() or "ویدیو جدید"
                        
                        # پیدا کردن تصویر
                        img = link.find_element(By.XPATH, "ancestor::*//img | preceding::img")
                        img_url = img.get_attribute('src') if img else None
                        
                        new_posts.append({
                            'title': title,
                            'link': url,
                            'image': img_url
                        })
                    except:
                        pass
            except Exception as e:
                print(f"خطا در روش 2: {e}")
        
        driver.quit()
        
        # حذف آیتم‌های تکراری
        unique_posts = []
        seen = set()
        for post in new_posts:
            if post['link'] not in seen:
                seen.add(post['link'])
                unique_posts.append(post)
        
        print(f"{len(unique_posts)} ویدیو پیدا شد.")
        return unique_posts[:10]
        
    except Exception as e:
        print(f"خطا در راه‌اندازی مرورگر: {e}")
        return []

def send_to_telegram(post):
    """ارسال پست به تلگرام"""
    caption = f"{post['title']}\n{post['link']}"
    
    if post.get('image') and post['image'].startswith('http'):
        try:
            response = requests.post(
                f"{TELEGRAM_API_URL}/sendPhoto",
                data={'chat_id': CHAT_ID, 'caption': caption},
                files={'photo': requests.get(post['image']).content}
            )
            if response.ok:
                return
        except Exception as e:
            print(f"خطا در ارسال عکس: {e}")
    
    # ارسال به صورت متن
    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        data={'chat_id': CHAT_ID, 'text': caption}
    )

def main():
    print("شروع اسکرپینگ با Selenium...")
    sent_links = load_sent_links()
    all_posts = get_new_posts()
    
    if not all_posts:
        print("هیچ پستی پیدا نشد.")
        return

    posts_to_send = [p for p in all_posts if p['link'] not in sent_links]
    print(f"{len(posts_to_send)} پست جدید برای ارسال پیدا شد.")

    for post in posts_to_send[:10]:
        try:
            send_to_telegram(post)
            sent_links.add(post['link'])
            time.sleep(2)
        except Exception as e:
            print(f"خطا در ارسال: {e}")

    save_sent_links(sent_links)
    print("پایان کار.")

if __name__ == "__main__":
    main()
