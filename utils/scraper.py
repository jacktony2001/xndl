import time
import logging
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

logger = logging.getLogger(__name__)

class AznudeScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.video_url = None

    def _init_driver(self):
        """راه‌اندازی مرورگر با تنظیمات استاندارد"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def get_list_page_links(self, url):
        """دریافت لینک‌های صفحه لیست (فقط /view/celeb/ یا /view/movie/)"""
        logger.info(f"🔍 Scanning list page: {url}")
        self.driver = self._init_driver()
        links = []
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(5)

            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    if not href:
                        continue
                    if ('/view/celeb/' in href or '/view/movie/' in href) and '/azncdn/' not in href:
                        title = link.text.strip() or "مطلب جدید"
                        if not any(item['link'] == href for item in links):
                            links.append({'title': title, 'link': href})
                except:
                    continue

            logger.info(f"✅ Found {len(links)} valid video links")
            return links

        except Exception as e:
            logger.error(f"❌ Error in get_list_page_links: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()

    def extract_main_video(self, page_url):
        """
        استخراج ویدیوی اصلی از صفحه فیلم با استفاده از سلکتور دقیق
        فقط ویدیویی که داخل بخش اصلی فیلم قرار داره رو برمیداره
        """
        logger.info(f"📄 Extracting video from: {page_url}")
        self.driver = self._init_driver()
        
        try:
            self.driver.get(page_url)
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # اسکرول برای بارگذاری کامل
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(5)
            
            # پیدا کردن بخش اصلی فیلم (با کلاس یا آیدی مخصوص)
            # معمولاً بخش اصلی فیلم در یک div با کلاس video-container یا player-container قرار داره
            main_video_container = None
            try:
                # روش ۱: جستجوی کانتینر اصلی فیلم
                main_video_container = self.driver.find_element(By.CSS_SELECTOR, ".single-video-player-container, .player-container, .jwplayer, .video-container")
            except:
                try:
                    # روش ۲: جستجوی دکمه پخش که فقط در بخش اصلی وجود داره
                    play_button = self.driver.find_element(By.CSS_SELECTOR, ".jw-icon.jw-icon-display, .vjs-big-play-button")
                    main_video_container = play_button.find_element(By.XPATH, "./ancestor::div[contains(@class, 'player') or contains(@class, 'video')]")
                except:
                    # روش ۳: اگر هیچ کدوم پیدا نشد، کل صفحه رو در نظر بگیر
                    main_video_container = self.driver.find_element(By.TAG_NAME, "body")
            
            # پیدا کردن تگ video داخل کانتینر اصلی
            video = main_video_container.find_element(By.TAG_NAME, "video")
            video_url = video.get_attribute('src')
            
            # اگر src خالی بود، تگ source رو چک کن
            if not video_url or not video_url.startswith('http'):
                try:
                    source = main_video_container.find_element(By.XPATH, ".//video/source")
                    video_url = source.get_attribute('src')
                except:
                    pass
            
            # اعتبارسنجی نهایی
            if video_url and video_url.startswith('http') and ('cdn' in video_url or '.mp4' in video_url):
                logger.info(f"✅ Main video found: {video_url[:80]}...")
                self.driver.quit()
                return video_url
            else:
                logger.warning(f"⚠️ No valid video found in main container for {page_url}")
                self.driver.quit()
                return None

        except Exception as e:
            logger.error(f"❌ Error in extract_main_video: {e}")
            if self.driver:
                self.driver.quit()
            return None
        finally:
            if self.driver:
                self.driver.quit()
