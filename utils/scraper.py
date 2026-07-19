import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
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
        self.driver = None

    def start(self):
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.driver.set_page_load_timeout(30)

    def stop(self):
        if self.driver:
            self.driver.quit()

    def get_new_videos(self, url):
        """Get video links from the recent page, filtering out ads"""
        self.start()
        try:
            self.driver.get(url)
            time.sleep(3)  # Let page load fully

            # Find all video items
            items = self.driver.find_elements(By.CSS_SELECTOR, 'div.video-item, div.thumb-item, article, div[class*="video"], div[class*="thumb"]')
            
            video_links = []
            for item in items:
                # Check for AD or Sponsored labels
                item_text = item.text.lower()
                if 'ad' in item_text or 'sponsored' in item_text:
                    continue

                # Find link
                link_elem = item.find_element(By.TAG_NAME, 'a')
                href = link_elem.get_attribute('href')
                if not href:
                    continue

                # Only accept /view/celeb/ or /view/movie/
                if '/view/celeb/' in href or '/view/movie/' in href:
                    title = link_elem.text.strip() or 'Untitled'
                    video_links.append({
                        'url': href,
                        'title': title
                    })

            logger.info(f"Found {len(video_links)} valid video links")
            return video_links

        except Exception as e:
            logger.error(f"Error scraping: {e}")
            return []
        finally:
            self.stop()

    def extract_video_url(self, video_page_url):
        """Extract direct video URL from a /view/celeb/ or /view/movie/ page"""
        self.start()
        try:
            self.driver.get(video_page_url)
            time.sleep(3)

            # Try to find video source
            video = self.driver.find_element(By.TAG_NAME, 'video')
            sources = video.find_elements(By.TAG_NAME, 'source')
            
            for source in sources:
                src = source.get_attribute('src')
                if src and not src.endswith('.mp4'):  # sometimes ads have weird extensions
                    continue
                if src:
                    return src

            # Fallback: check video src directly
            video_src = video.get_attribute('src')
            if video_src:
                return video_src

            # Fallback: look for any video URL in the page
            scripts = self.driver.find_elements(By.TAG_NAME, 'script')
            for script in scripts:
                content = script.get_attribute('innerHTML')
                if content:
                    matches = re.findall(r'https?://[^\s"\']+\.(?:mp4|webm|m3u8)', content)
                    if matches:
                        return matches[0]

            return None

        except Exception as e:
            logger.error(f"Error extracting video from {video_page_url}: {e}")
            return None
        finally:
            self.stop()
