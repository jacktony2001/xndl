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

    def _init_driver_with_cdp(self):
        """راه‌اندازی مرورگر با فعال‌سازی CDP برای مانیتورینگ شبکه"""
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
        
        # فعال‌سازی logging برای دریافت درخواست‌های شبکه
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _listen_for_mp4(self, driver, timeout=15):
        """شنود درخواست‌های شبکه و پیدا کردن اولین فایل mp4"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                logs = driver.get_log('performance')
                for log in logs:
                    try:
                        log_data = json.loads(log['message'])
                        message = log_data.get('message', {})
                        method = message.get('method', '')
                        
                        if method == 'Network.responseReceived':
                            response = message.get('params', {}).get('response', {})
                            url = response.get('url', '')
                            
                            if '.mp4' in url and 'cdn' in url:
                                logger.info(f"🎬 MP4 request detected: {url}")
                                return url
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.debug(f"Error parsing log: {e}")
                        continue
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Error getting logs: {e}")
                time.sleep(0.5)
        
        return None

    def get_list_page_links(self, url):
        """دریافت لینک‌های صفحه لیست (فقط /view/celeb/ یا /view/movie/)"""
        logger.info(f"🔍 Scanning list page: {url}")
        self.driver = self._init_driver_with_cdp()
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

    def extract_main_video_with_cdp(self, page_url):
        """
        استخراج ویدیوی اصلی با استفاده از CDP و شنود درخواست‌های شبکه
        اولین فایل mp4 که مرورگر درخواست می‌کند، ویدیوی اصلی است
        """
        logger.info(f"📄 Extracting video from: {page_url}")
        self.driver = self._init_driver_with_cdp()
        
        try:
            self.driver.get(page_url)
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(3)
            
            # کلیک روی دکمه پخش اگر وجود داشت
            try:
                play_button = self.driver.find_element(By.CSS_SELECTOR, ".jw-icon.jw-icon-display, .jw-svg-icon-play, .vjs-big-play-button")
                self.driver.execute_script("arguments[0].click();", play_button)
                logger.info("▶️ Clicked on play button")
            except:
                logger.info("ℹ️ No play button found or already playing")
            
            logger.info("🎧 Listening for MP4 requests...")
            video_url = self._listen_for_mp4(self.driver, timeout=15)
            
            if video_url:
                logger.info(f"✅ Main video found: {video_url[:80]}...")
                self.driver.quit()
                return video_url
            else:
                logger.warning(f"⚠️ No MP4 request detected for {page_url}")
                self.driver.quit()
                return None

        except Exception as e:
            logger.error(f"❌ Error in extract_main_video_with_cdp: {e}")
            if self.driver:
                self.driver.quit()
            return None
        finally:
            if self.driver:
                self.driver.quit()
