import os
import json
import requests
from bs4 import BeautifulSoup
from time import sleep
import random

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
    """سایت را با هدرهای کامل و کوکی شبیه‌سازی شده اسکرپ می‌کند."""
    
    # هدرهای کامل یک مرورگر واقعی
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    
    # کوکی‌های اولیه برای شبیه‌سازی یک بازدیدکننده واقعی
    cookies = {
        'aznude_session': '1',  # کوکی فرضی برای نشست
        'visitor_id': str(random.randint(1000000, 9999999)),
        'device_type': 'desktop',
        'theme': 'dark'  # یا 'light'
    }
    
    session = requests.Session()
    
    # ابتدا یک درخواست مقدماتی برای دریافت کوکی‌های اولیه
    try:
        session.get(SITE_URL, headers=headers, timeout=15)
    except:
        pass
    
    try:
        response = session.get(SITE_URL, headers=headers, cookies=cookies, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"خطا در دریافت صفحه: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    new_posts = []
    
    # پیدا کردن ویدیوهای جدید - بر اساس ساختار صفحه
    video_containers = []
    
    # روش 1: جستجوی بخش "Videos Added on"
    for section_title in soup.find_all(['h2', 'h3', 'h4']):
        if 'Videos Added on' in section_title.get_text():
            parent = section_title.find_parent()
            if parent:
                # پیدا کردن تمام آیتم‌های ویدیو در این بخش
                video_containers = parent.find_all(['li', 'div'], recursive=True)
                break
    
    # روش 2: اگر روش 1 موفق نشد، تمام آیتم‌های ویدیو را پیدا کن
    if not video_containers:
        # جستجوی آیتم‌هایی که شامل تگ ویدیو یا تصویر هستند
        video_containers = soup.find_all(['li', 'div'], class_=re.compile(r'(video|item|post|entry)', re.I))
    
    # اگر باز هم چیزی پیدا نشد، تمام لینک‌های حاوی /video/ را بررسی کن
    if not video_containers:
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            if '/video/' in href or '/watch/' in href or '/view/' in href:
                # یک المان ساختگی برای این لینک بساز
                container = soup.new_tag('div')
                container.append(link)
                img = link.find('img')
                if img:
                    container.append(img)
                video_containers.append(container)
    
    for item in video_containers[:20]:  # بررسی حداکثر 20 آیتم
        try:
            # پیدا کردن لینک اصلی
            link_tag = item.find('a', href=True)
            if not link_tag:
                continue
                
            post_url = link_tag.get('href')
            if not post_url:
                continue
                
            # اطمینان از کامل بودن لینک
            if post_url.startswith('/'):
                post_url = 'https://aznude.com' + post_url
            elif not post_url.startswith('http'):
                post_url = 'https://aznude.com/' + post_url
            
            # پیدا کردن تصویر
            img_tag = item.find('img')
            img_url = None
            if img_tag and img_tag.get('src'):
                img_url = img_tag.get('src')
                if img_url.startswith('/'):
                    img_url = 'https://aznude.com' + img_url
                elif not img_url.startswith('http'):
                    img_url = 'https://aznude.com/' + img_url
            
            # پیدا کردن عنوان
            title = link_tag.get_text(strip=True)
            if not title and img_tag and img_tag.get('alt'):
                title = img_tag.get('alt')
            if not title:
                # استخراج عنوان از لینک
                title_parts = post_url.strip('/').split('/')
                if title_parts:
                    title = title_parts[-1].replace('-', ' ').title()
                else:
                    title = "ویدیو جدید"
            
            # اضافه کردن به لیست
            new_posts.append({
                'title': title[:100],  # محدود کردن طول عنوان
                'link': post_url,
                'image': img_url
            })
            
        except Exception as e:
            print(f"خطا در پردازش یک آیتم: {e}")
            continue
    
    # حذف آیتم‌های تکراری
    unique_posts = []
    seen_links = set()
    for post in new_posts:
        if post['link'] not in seen_links:
            seen_links.add(post['link'])
            unique_posts.append(post)
    
    return unique_posts[:10]  # فقط ۱۰ مورد اول را برگردان

def send_to_telegram(post):
    """یک پست را به تلگرام ارسال می‌کند."""
    caption = f"🎬 {post['title']}\n🔗 {post['link']}"
    
    if post.get('image'):
        try:
            # دانلود و ارسال با عکس
            img_response = requests.get(post['image'], timeout=15)
            if img_response.status_code == 200:
                response = requests.post(
                    f"{TELEGRAM_API_URL}/sendPhoto",
                    data={'chat_id': CHAT_ID, 'caption': caption},
                    files={'photo': ('image.jpg', img_response.content, 'image/jpeg')}
                )
                if response.ok:
                    return
                else:
                    print(f"خطا در ارسال عکس: {response.text}")
            else:
                print(f"خطا در دانلود عکس: {img_response.status_code}")
        except Exception as e:
            print(f"خطا در ارسال عکس: {e}")
    
    # در صورت خطا یا نبود عکس، به صورت متن ارسال کن
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': caption}
        )
        if not response.ok:
            print(f"خطا در ارسال متن: {response.text}")
    except Exception as e:
        print(f"خطا در ارسال متن: {e}")

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
    for idx, post in enumerate(posts_to_send[:10]):
        try:
            print(f"ارسال پست {idx+1}: {post['title']}")
            send_to_telegram(post)
            sent_links.add(post['link'])
            sleep(3)  # تاخیر ۳ ثانیه‌ای بین ارسال‌ها
        except Exception as e:
            print(f"خطا در ارسال پست {post['link']}: {e}")

    save_sent_links(sent_links)
    print("پایان کار.")

if __name__ == "__main__":
    main()
