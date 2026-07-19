import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
    """استفاده از selenium با کروم دایرکت"""
    print("راه‌اندازی مرورگر...")
    
    # تنظیمات مرورگر بدون رابط کاربری
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # استفاده از مسیر مستقیم کروم‌درایور
        from selenium.webdriver.chrome.service import Service
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"بارگذاری صفحه {SITE_URL}...")
        driver.get(SITE_URL)
        
        # منتظر بارگذاری محتوا
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(8)  # افزایش زمان برای بارگذاری محتوای داینامیک
        
        # پیدا کردن ویدیوها
        new_posts = []
        
        # روش 1: پیدا کردن بخش "Videos Added on"
        try:
            sections = driver.find_elements(By.XPATH, "//*[contains(text(), 'Videos Added on')]")
            if sections:
                parent = sections[0].find_element(By.XPATH, "..")
                video_items = parent.find_elements(By.XPATH, ".//a[contains(@href, '/video/') or contains(@href, '/watch/')]")
                
                for item in video_items[:15]:
                    try:
                        link = item.get_attribute('href')
                        title = item.text.strip() or "ویدیو جدید"
                        
                        # پیدا کردن تصویر
                        try:
                            img = item.find_element(By.XPATH, ".//img | ../img")
                            img_url = img.get_attribute('src') if img else None
                        except:
                            img_url = None
                        
                        if link:
                            new_posts.append({
                                'title': title,
                                'link': link,
                                'image': img_url
                            })
                    except Exception as e:
                        print(f"خطا در استخراج آیتم: {e}")
        except Exception as e:
            print(f"خطا در روش 1: {e}")
        
        # روش 2: اگر روش اول موفق نشد، همه لینک‌ها را بررسی کن
        if not new_posts:
            try:
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links[:30]:
                    try:
                        href = link.get_attribute('href')
                        if href and ('/video/' in href or '/watch/' in href):
                            title = link.text.strip() or "ویدیو جدید"
                            img_url = None
                            try:
                                img = link.find_element(By.XPATH, "..//img")
                                img_url = img.get_attribute('src') if img else None
                            except:
                                pass
                            
                            new_posts.append({
                                'title': title,
                                'link': href,
                                'image': img_url
                            })
                    except:
                        pass
            except Exception as e:
                print(f"خطا در روش 2: {e}")
        
        driver.quit()
        
        # حذف تکراری‌ها
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
    caption = f"{post['title']}\n{post['link']}"
    
    if post.get('image') and post['image'] and post['image'].startswith('http'):
        try:
            img_data = requests.get(post['image'], timeout=10)
            if img_data.status_code == 200:
                response = requests.post(
                    f"{TELEGRAM_API_URL}/sendPhoto",
                    data={'chat_id': CHAT_ID, 'caption': caption},
                    files={'photo': ('image.jpg', img_data.content, 'image/jpeg')}
                )
                if response.ok:
                    return
        except Exception as e:
            print(f"خطا در ارسال عکس: {e}")
    
    # ارسال متن
    try:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': caption}
        )
    except Exception as e:
        print(f"خطا در ارسال متن: {e}")

def main():
    print("شروع اسکرپینگ...")
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
