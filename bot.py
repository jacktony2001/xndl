import os
import json
import requests
from bs4 import BeautifulSoup
from time import sleep
import re

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
    """سایت را با هدرهای واقعی‌تر اسکرپ کرده و لیست ویدیوهای جدید را برمی‌گرداند."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    # ایجاد یک نشست (Session) برای نگهداری کوکی‌ها
    session = requests.Session()
    try:
        response = session.get(SITE_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"خطا در دریافت صفحه: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    new_posts = []
    
    # پیدا کردن بخش "Videos Added on" که حاوی ویدیوهای جدید است
    # بر اساس محتوای ارسالی، ویدیوها در یک بخش با عنوان "Videos Added on" قرار دارند
    videos_section = None
    for h3 in soup.find_all(['h2', 'h3', 'h4']):
        if 'Videos Added on' in h3.get_text():
            videos_section = h3.find_parent()
            break
    
    if not videos_section:
        print("بخش ویدیوهای جدید پیدا نشد. کل صفحه بررسی می‌شود.")
        videos_section = soup  # اگر بخش پیدا نشد، کل صفحه را بررسی کن
    
    # پیدا کردن آیتم‌های ویدیو - بر اساس ساختار صفحه، هر ویدیو در یک <li> یا <div> است
    # در صفحه ارسالی، ویدیوها به صورت لیست با تگ‌های <a> و تصویر هستند
    video_items = videos_section.find_all(['li', 'div'], recursive=True)
    
    for item in video_items:
        # بررسی اینکه آیتم دارای لینک و تصویر باشد
        link_tag = item.find('a', href=True)
        if not link_tag:
            continue
            
        # بررسی اینکه لینک به یک ویدیو اشاره داشته باشد (معمولاً شامل /video/ یا /watch/ است)
        post_url = link_tag.get('href')
        if not post_url or not ('/video/' in post_url or '/watch/' in post_url or '/view/' in post_url):
            continue
            
        if not post_url.startswith('http'):
            post_url = 'https://aznude.com' + post_url if post_url.startswith('/') else SITE_URL + '/' + post_url
        
        # پیدا کردن تصویر
        img_tag = item.find('img')
        img_url = None
        if img_tag and img_tag.get('src'):
            img_url = img_tag.get('src')
            if img_url and not img_url.startswith('http'):
                img_url = 'https://aznude.com' + img_url if img_url.startswith('/') else SITE_URL + '/' + img_url
        
        # پیدا کردن عنوان (متن داخل لینک یا ویژگی alt تصویر)
        title = link_tag.get_text(strip=True)
        if not title and img_tag and img_tag.get('alt'):
            title = img_tag.get('alt')
        if not title:
            title = "ویدیو جدید"
            
        # استخراج نام بازیگر و فیلم از عنوان یا لینک (اختیاری)
        # می‌توانید این بخش را بر اساس نیاز خود تغییر دهید
        new_posts.append({
            'title': title,
            'link': post_url,
            'image': img_url
        })
    
    # حذف آیتم‌های تکراری بر اساس لینک
    unique_posts = []
    seen_links = set()
    for post in new_posts:
        if post['link'] not in seen_links:
            seen_links.add(post['link'])
            unique_posts.append(post)
    
    return unique_posts[:15]  # برگرداندن حداکثر ۱۵ آیتم برای اطمینان

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
    all_posts = get_new_posts()
    
    if not all_posts:
        print("هیچ پستی پیدا نشد.")
        return

    # فیلتر کردن پست‌های قبلاً ارسال نشده
    posts_to_send = [p for p in all_posts if p['link'] not in sent_links]
    print(f"{len(posts_to_send)} پست جدید برای ارسال پیدا شد.")

    # ارسال حداکثر ۱۰ پست
    for post in posts_to_send[:10]:
        try:
            send_to_telegram(post)
            sent_links.add(post['link'])
            sleep(2)  # تاخیر ۲ ثانیه‌ای برای جلوگیری از محدودیت
        except Exception as e:
            print(f"خطا در ارسال پست {post['link']}: {e}")

    save_sent_links(sent_links)
    print("پایان کار.")

if __name__ == "__main__":
    main()
