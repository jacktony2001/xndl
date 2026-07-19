import os
import json
import requests
from bs4 import BeautifulSoup
from time import sleep

# --- تنظیمات برگرفته از Secrets گیت‌هاب ---
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')  # توکن ربات از گیت‌هاب می‌آید
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')      # آی‌دی چت از گیت‌هاب می‌آید

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("لطفاً TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID را در Secrets تنظیم کنید.")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SITE_URL = "https://aznude.com"  # آدرس سایت مورد نظر شما

# فایل برای ذخیره لینک‌های ارسال شده (برای جلوگیری از ارسال تکراری)
SENT_FILE = "sent_links.json"

def load_sent_links():
    """لینک‌های ارسال شده را از فایل بارگذاری می‌کند."""
    try:
        with open(SENT_FILE, 'r') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent_links(links):
    """لینک‌های ارسال شده را در فایل ذخیره می‌کند."""
    with open(SENT_FILE, 'w') as f:
        json.dump(list(links), f)

def get_new_posts():
    """
    سایت را اسکرپ کرده و لیستی از پست‌های جدید (با عنوان، لینک و آدرس تصویر) برمی‌گرداند.
    این تابع را بر اساس ساختار سایت aznude.com شخصی‌سازی کنید.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(SITE_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"خطا در دریافت صفحه: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    new_posts = []
    
    # *** این بخش را بر اساس ساختار سایت مورد نظر تغییر دهید ***
    # مثال: فرض می‌کنیم هر پست جدید در یک تگ <div class="post-item"> قرار دارد
    post_items = soup.select('.post-item')  # سلکتور مناسب را پیدا کنید
    
    for item in post_items[:10]:  # فقط ۱۰ مورد اول
        try:
            # لینک پست
            link_tag = item.find('a')
            if not link_tag:
                continue
            post_url = link_tag.get('href')
            if not post_url:
                continue
            if not post_url.startswith('http'):
                post_url = SITE_URL + post_url
                
            # عنوان
            title = link_tag.get_text(strip=True) or "بدون عنوان"
            
            # تصویر (آدرس عکس یا ویدیو)
            img_tag = item.find('img')
            img_url = img_tag.get('src') if img_tag else None
            if img_url and not img_url.startswith('http'):
                img_url = SITE_URL + img_url

            new_posts.append({
                'title': title,
                'link': post_url,
                'image': img_url
            })
        except Exception as e:
            print(f"خطا در پردازش یک آیتم: {e}")
            continue
            
    return new_posts

def send_to_telegram(post):
    """یک پست را به تلگرام ارسال می‌کند."""
    caption = f"{post['title']}\n{post['link']}"
    
    if post.get('image'):
        try:
            # ارسال با عکس
            response = requests.post(
                f"{TELEGRAM_API_URL}/sendPhoto",
                data={'chat_id': CHAT_ID, 'caption': caption},
                files={'photo': requests.get(post['image']).content}
            )
            if not response.ok:
                raise Exception("ارسال عکس失敗")
            return
        except Exception as e:
            print(f"خطا در ارسال عکس: {e}. ارسال به صورت متن...")
    
    # در صورت خطا یا نبود عکس، به صورت متن ارسال کن
    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        data={'chat_id': CHAT_ID, 'text': caption}
    )

def main():
    print("شروع اسکرپینگ...")
    sent_links = load_sent_links()
    new_posts = get_new_posts()
    
    if not new_posts:
        print("هیچ پست جدیدی پیدا نشد.")
        return

    # فیلتر کردن پست‌های قبلاً ارسال نشده
    posts_to_send = [p for p in new_posts if p['link'] not in sent_links]
    print(f"{len(posts_to_send)} پست جدید برای ارسال پیدا شد.")

    for post in posts_to_send[:10]:  # حداکثر ۱۰ پست
        try:
            send_to_telegram(post)
            sent_links.add(post['link'])
            sleep(1)  # تاخیر یک ثانیه‌ای بین ارسال‌ها
        except Exception as e:
            print(f"خطا در ارسال پست {post['link']}: {e}")

    save_sent_links(sent_links)
    print("پایان کار.")

if __name__ == "__main__":
    main()
