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

    def _is_valid_video_url(self, url):
        """Check if URL is a valid main video (not an ad)"""
        if not url:
            return False
        
        # Must be video format
        if not any(ext in url.lower() for ext in ['.mp4', '.webm', '.m3u8']):
            return False
        
        # Skip ad URLs
        ad_patterns = [
            'ad',
            'ads',
            'sponsored',
            'promo',
            'preroll',
            'postroll',
            'adserver',
            'adservice',
            'doubleclick',
            'googleads',
            'adnxs',
            'advertisement',
            'pre-roll',
            'banner',
            'stripchat',
            'ourdream',
            'sexselector',
            'lustgoddess',
            '蓝猫'
        ]
        
        url_lower = url.lower()
        for pattern in ad_patterns:
            if pattern in url_lower:
                logger.debug(f"Skipping ad URL: {url}")
                return False
        
        # Prefer URLs from main CDN
        if 'bkcdn.net' in url_lower:
            return True
        
        # Allow other CDNs but log them
        logger.debug(f"Non-standard CDN: {url}")
        return True

    def _is_ad_element(self, element):
        """Check if an element is inside an ad container"""
        try:
            # Check parent chain for ad indicators
            parent_check = self.driver.execute_script("""
                var el = arguments[0];
                var maxDepth = 5;
                while (el && maxDepth > 0) {
                    var classes = el.className || '';
                    var id = el.id || '';
                    var text = el.innerText || '';
                    var combined = (classes + ' ' + id + ' ' + text).toLowerCase();
                    if (combined.includes('ad') || 
                        combined.includes('sponsored') || 
                        combined.includes('promo') ||
                        combined.includes('banner') ||
                        combined.includes('stripchat') ||
                        combined.includes('ourdream')) {
                        return true;
                    }
                    el = el.parentElement;
                    maxDepth--;
                }
                return false;
            """, element)
            return parent_check
        except:
            return False

    def get_new_videos(self, url):
        self.start()
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)

            # Find all links that start with /view/celeb/ or /view/movie/
            all_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="/view/celeb/"], a[href^="/view/movie/"]')
            
            video_links = []
            seen_urls = set()
            
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    if not href or href in seen_urls:
                        continue
                    
                    # Skip if link is in ad container
                    if self._is_ad_element(link):
                        continue
                    
                    seen_urls.add(href)
                    
                    # Get title - try multiple methods
                    title = link.text.strip()
                    if not title:
                        # Try parent or sibling text
                        try:
                            parent = link.find_element(By.XPATH, '..')
                            title = parent.text.strip()
                            # Clean up title - remove extra text
                            title = re.sub(r'\s+', ' ', title)
                            # If title has multiple lines, take the first non-empty one
                            lines = [l.strip() for l in title.split('\n') if l.strip()]
                            if lines:
                                title = lines[0]
                        except:
                            title = 'Untitled'
                    
                    if not title or title == 'Untitled':
                        # Try to get from nearby element
                        try:
                            nearby = link.find_element(By.XPATH, './following-sibling::*[1]')
                            title = nearby.text.strip() or 'Untitled'
                        except:
                            pass
                    
                    video_links.append({
                        'url': href,
                        'title': title[:100]
                    })
                    logger.info(f"Found video: {title[:50]}...")
                    
                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
                    continue

            # Remove duplicates while preserving order
            seen = set()
            unique_links = []
            for v in video_links:
                if v['url'] not in seen:
                    seen.add(v['url'])
                    unique_links.append(v)
            
            logger.info(f"Found {len(unique_links)} valid video links")
            return unique_links

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
            
            # Scroll to load lazy content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            video_url = None
            
            # Find all video elements
            videos = self.driver.find_elements(By.TAG_NAME, 'video')
            
            # Filter out ad videos
            valid_videos = []
            for video in videos:
                if not self._is_ad_element(video):
                    valid_videos.append(video)
            
            # Try to get video URL from valid videos
            for video in valid_videos:
                # Check sources first
                sources = video.find_elements(By.TAG_NAME, 'source')
                for source in sources:
                    src = source.get_attribute('src')
                    if src and self._is_valid_video_url(src):
                        video_url = src
                        break
                
                # Check video src directly
                if not video_url:
                    src = video.get_attribute('src')
                    if src and self._is_valid_video_url(src):
                        video_url = src
                
                if video_url:
                    break
            
            # If no video found in valid elements, try searching the page
            if not video_url:
                # Look for video URLs in any src attributes
                elements = self.driver.find_elements(By.XPATH, "//*[@src]")
                for elem in elements:
                    if self._is_ad_element(elem):
                        continue
                    
                    for attr in ['src', 'data-src', 'data-video', 'data-url']:
                        try:
                            src = elem.get_attribute(attr)
                            if src and self._is_valid_video_url(src):
                                video_url = src
                                break
                        except:
                            pass
                    if video_url:
                        break
            
            # Look in scripts as last resort
            if not video_url:
                scripts = self.driver.find_elements(By.TAG_NAME, 'script')
                for script in scripts:
                    content = script.get_attribute('innerHTML')
                    if content:
                        matches = re.findall(r'https?://[^\s"\']+\.(?:mp4|webm|m3u8)', content)
                        for match in matches:
                            if self._is_valid_video_url(match):
                                video_url = match
                                break
                    if video_url:
                        break

            if video_url:
                logger.info(f"Extracted video URL: {video_url[:100]}...")
            else:
                logger.warning(f"No valid video found on {video_page_url}")

            return video_url

        except Exception as e:
            logger.error(f"Error extracting video from {video_page_url}: {e}")
            return None
        finally:
            self.stop()
