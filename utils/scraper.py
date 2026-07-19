import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AznudeScraper:
    def __init__(self, headless=True):
        self.options = Options()
        if headless:
            self.options.add_argument('--headless=new')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.driver = None

    def start(self):
        service = Service(executable_path='/usr/local/bin/chromedriver')
        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.driver.set_page_load_timeout(30)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def stop(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def get_new_videos(self, url):
        self.start()
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)

            all_links = self.driver.find_elements(By.TAG_NAME, 'a')
            video_links = []
            seen_urls = set()
            
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    if not href:
                        continue
                    
                    if '/view/celeb/' in href or '/view/movie/' in href:
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)
                        
                        title = link.text.strip()
                        if not title:
                            try:
                                parent = link.find_element(By.XPATH, '..')
                                title = parent.text.strip() or 'Untitled'
                            except:
                                title = 'Untitled'
                        
                        parent_text = self.driver.execute_script(
                            "return arguments[0].closest('div, article, li')?.innerText || ''", 
                            link
                        )
                        if 'ad' in parent_text.lower() or 'sponsored' in parent_text.lower():
                            continue
                        
                        video_links.append({
                            'url': href,
                            'title': title[:100]
                        })
                        logger.info(f"Found video: {title[:50]}...")
                except Exception:
                    continue

            logger.info(f"Found {len(video_links)} valid video links")
            return video_links

        except Exception as e:
            logger.error(f"Error scraping: {e}")
            return []
        finally:
            self.stop()

    def extract_video_url(self, video_page_url):
        self.start()
        try:
            self.driver.get(video_page_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(5)
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            video_url = None
            
            # Method 1: video tag
            try:
                video = self.driver.find_element(By.TAG_NAME, 'video')
                sources = video.find_elements(By.TAG_NAME, 'source')
                for source in sources:
                    src = source.get_attribute('src')
                    if src and any(ext in src for ext in ['.mp4', '.webm', '.m3u8']):
                        video_url = src
                        break
                if not video_url:
                    video_url = video.get_attribute('src')
            except:
                pass

            # Method 2: src/data attributes
            if not video_url:
                elements = self.driver.find_elements(By.XPATH, "//*[@src or @data-src or @data-video]")
                for elem in elements:
                    for attr in ['src', 'data-src', 'data-video', 'data-url']:
                        try:
                            src = elem.get_attribute(attr)
                            if src and any(ext in src for ext in ['.mp4', '.webm', '.m3u8']):
                                video_url = src
                                break
                        except:
                            pass
                    if video_url:
                        break

            # Method 3: scripts
            if not video_url:
                scripts = self.driver.find_elements(By.TAG_NAME, 'script')
                for script in scripts:
                    content = script.get_attribute('innerHTML')
                    if content:
                        matches = re.findall(r'https?://[^\s"\']+\.(?:mp4|webm|m3u8)', content)
                        if matches:
                            video_url = matches[0]
                            break

            # Method 4: JS objects
            if not video_url:
                scripts = self.driver.find_elements(By.TAG_NAME, 'script')
                for script in scripts:
                    content = script.get_attribute('innerHTML')
                    if content:
                        matches = re.findall(r'["\'](https?://[^"\']+\.(?:mp4|webm|m3u8))["\']', content)
                        if matches:
                            video_url = matches[0]
                            break

            # Method 5: iframes
            if not video_url:
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                for iframe in iframes:
                    src = iframe.get_attribute('src')
                    if src and 'player' in src.lower():
                        try:
                            self.driver.switch_to.frame(iframe)
                            time.sleep(1)
                            video = self.driver.find_element(By.TAG_NAME, 'video')
                            src = video.get_attribute('src')
                            if src:
                                video_url = src
                                break
                        except:
                            pass
                        finally:
                            self.driver.switch_to.default_content()

            if video_url:
                logger.info(f"Extracted video URL: {video_url[:100]}...")
            else:
                logger.warning(f"No video found on {video_page_url}")

            return video_url

        except Exception as e:
            logger.error(f"Error extracting video from {video_page_url}: {e}")
            return None
        finally:
            self.stop()
