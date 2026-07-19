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

def debug_get_all_links():
    """دریافت و نمایش تمام لینک‌های موجود در صفحه به همراه اطلاعات"""
    print("🔍 شروع دیباگ...")
    
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
        
        print(f"📄 بارگذاری صفحه: {TARGET_URL}")
        driver.get(TARGET_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)
        
        # پیدا کردن تمام لینک‌ها
        all_links = driver.find_elements(By.TAG_NAME, "a")
        
        print("\n" + "="*80)
        print("📊 تمام لینک‌های موجود در صفحه:")
        print("="*80)
        
        filtered_links = []
        for i, link in enumerate(all_links):
            try:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href:
                    # فقط لینک‌هایی که مربوط به محتوا هستن
                    if '/view/celeb/' in href or '/view/movie/' in href or '/azncdn/' in href:
                        filtered_links.append({
                            'index': i,
                            'href': href,
                            'text': text
                        })
                        # چاپ با جزئیات
                        is_azncdn = "⚠️ تبلیغات" if '/azncdn/' in href else "✅ اصلی"
                        print(f"[{i}] {is_azncdn}")
                        print(f"    لینک: {href}")
                        print(f"    متن: {text[:50] if text else '(بدون متن)'}")
                        print("-" * 60)
            except:
                pass
        
        print("="*80)
        print(f"📊 خلاصه:")
        print(f"   ✅ لینک‌های اصلی (/view/celeb/ یا /view/movie/): {len([l for l in filtered_links if '/view/' in l['href'] and '/azncdn/' not in l['href']])}")
        print(f"   ⚠️ لینک‌های تبلیغاتی (/azncdn/): {len([l for l in filtered_links if '/azncdn/' in l['href']])}")
        print("="*80)
        
        # ۱۰ تا از اصلی‌ها رو نشون بده
        print("\n✅ ۱۰ لینک اصلی اول:")
        main_links = [l for l in filtered_links if '/view/' in l['href'] and '/azncdn/' not in l['href']]
        for i, link in enumerate(main_links[:10]):
            print(f"  {i+1}. {link['href']}")
        
        driver.quit()
        
    except Exception as e:
        print(f"❌ خطا: {e}")

def main():
    print("🚀 شروع دیباگ...")
    debug_get_all_links()
    print("\n✅ پایان دیباگ")

if __name__ == "__main__":
    main()
