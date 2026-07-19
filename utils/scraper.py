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

    def _is_advertisement(self, element):
        """Check if an element or its ancestors are advertisements"""
        try:
            # Get all classes, IDs, and text up the parent chain
            result = self.driver.execute_script("""
                var el = arguments[0];
                var maxDepth = 5;
                while (el && maxDepth > 0) {
                    var classes = el.className || '';
                    var id = el.id || '';
                    var text = (el.innerText || '').toLowerCase();
                    var combined = (classes + ' ' + id + ' ' + text).toLowerCase();
                    
                    // Check for ad indicators
                    var adPatterns = ['ad', 'sponsored', 'promo', 'banner', 'stripchat', 
                                     'ourdream', 'sexselector', 'lustgoddess', '广告', '赞助'];
                    for (var i = 0; i < adPatterns.length; i++) {
                        if (combined.includes(adPatterns[i])) {
                            return true;
                        }
                    }
                    el = el.parentElement;
                    maxDepth--;
                }
                return false;
            """, element)
            return result
        except:
            return False

    def _get_page_identifier(self):
        """Get a unique identifier for the current page (URL or title)"""
        try:
            url = self.driver.current_url
            # Extract the celeb/movie name from URL
            match = re.search(r'/view/(celeb|movie)/([^/]+)/?$', url)
            if match:
                return match.group(2)  # Return the name part
            return url
        except:
            return None

    def get_new_videos(self, url):
        """Get video links from the recent page"""
        self.start()
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)

            # Get ALL links on the page
            all_links = self.driver.find_elements(By.TAG_NAME, 'a')
            
            video_links = []
            seen_urls = set()
            
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    if not href:
                        continue
                    
                    # Check if href contains /view/celeb/ or /view/movie/
                    if '/view/celeb/' in href or '/view/movie/' in href:
                        if href in seen_urls:
                            continue
                        
                        # Skip if link is in ad container
                        if self._is_advertisement(link):
                            continue
                        
                        seen_urls.add(href)
                        
                        # Get title
                        title = link.text.strip()
                        if not title:
                            try:
                                parent = link.find_element(By.XPATH, '..')
                                title = parent.text.strip()
                                title = re.sub(r'\s+', ' ', title)
                                lines = [l.strip() for l in title.split('\n') if l.strip()]
                                if lines:
                                    title = lines[0]
                            except:
                                title = 'Untitled'
                        
                        video_links.append({
                            'url': href,
                            'title': title[:100]
                        })
                        logger.info(f"Found video: {title[:50]}...")
                        
                except Exception:
                    continue

            # Remove duplicates
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
        """Extract the main video URL from a /view/ page"""
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

            page_id = self._get_page_identifier()
            logger.info(f"Extracting video for page: {page_id}")

            # STRATEGY: Find video that's associated with the page content
            # Approach: Look for video elements that are near the page's main heading/title
            video_url = None

            # 1. Find the page title/heading
            title_element = None
            try:
                # Look for h1 that contains the celeb/movie name
                headings = self.driver.find_elements(By.TAG_NAME, 'h1')
                for h in headings:
                    if not self._is_advertisement(h):
                        title_element = h
                        break
            except:
                pass

            # 2. Find video elements that are in the same section as the title
            if title_element:
                try:
                    # Get the parent section that contains both the title and video
                    section = self.driver.execute_script("""
                        var el = arguments[0];
                        // Find the nearest section/article/div that contains the title
                        var parent = el.parentElement;
                        while (parent && parent.tagName != 'BODY') {
                            var tag = parent.tagName.toLowerCase();
                            if (tag === 'section' || tag === 'article' || 
                                tag === 'main' || tag === 'div') {
                                // Check if this parent contains a video
                                var videos = parent.querySelectorAll('video');
                                if (videos.length > 0) {
                                    return parent;
                                }
                            }
                            parent = parent.parentElement;
                        }
                        return null;
                    """, title_element)
                    
                    if section:
                        # Find videos in this section
                        videos = section.find_elements(By.TAG_NAME, 'video')
                        for video in videos:
                            if not self._is_advertisement(video):
                                sources = video.find_elements(By.TAG_NAME, 'source')
                                for source in sources:
                                    src = source.get_attribute('src')
                                    if src and self._is_main_video(src):
                                        video_url = src
                                        break
                                if not video_url:
                                    src = video.get_attribute('src')
                                    if src and self._is_main_video(src):
                                        video_url = src
                                if video_url:
                                    break
                except Exception as e:
                    logger.debug(f"Error finding video near title: {e}")

            # 3. If not found, look for video in the largest non-ad content area
            if not video_url:
                try:
                    # Find the largest content div that's not an ad
                    content_div = self.driver.execute_script("""
                        var divs = document.querySelectorAll('div');
                        var largest = null;
                        var largestArea = 0;
                        for (var i = 0; i < divs.length; i++) {
                            var rect = divs[i].getBoundingClientRect();
                            var area = rect.width * rect.height;
                            // Must be large enough and not an ad
                            if (area > 50000 && area < 1000000) {
                                var text = (divs[i].innerText || '').toLowerCase();
                                if (!text.includes('ad') && !text.includes('sponsored') &&
                                    !text.includes('stripchat') && !text.includes('ourdream')) {
                                    if (area > largestArea) {
                                        largest = divs[i];
                                        largestArea = area;
                                    }
                                }
                            }
                        }
                        return largest;
                    """)
                    
                    if content_div:
                        videos = content_div.find_elements(By.TAG_NAME, 'video')
                        for video in videos:
                            if not self._is_advertisement(video):
                                sources = video.find_elements(By.TAG_NAME, 'source')
                                for source in sources:
                                    src = source.get_attribute('src')
                                    if src and self._is_main_video(src):
                                        video_url = src
                                        break
                                if not video_url:
                                    src = video.get_attribute('src')
                                    if src and self._is_main_video(src):
                                        video_url = src
                                if video_url:
                                    break
                except Exception as e:
                    logger.debug(f"Error finding video in content area: {e}")

            # 4. Look for video in page source (JSON or script tags)
            if not video_url:
                try:
                    # Look for video URLs in script tags that contain the page identifier
                    scripts = self.driver.find_elements(By.TAG_NAME, 'script')
                    for script in scripts:
                        content = script.get_attribute('innerHTML')
                        if content and page_id and page_id in content:
                            # Look for video URLs
                            matches = re.findall(r'https?://[^\s"\']+\.(?:mp4|webm|m3u8)', content)
                            for match in matches:
                                if self._is_main_video(match):
                                    video_url = match
                                    break
                        if video_url:
                            break
                except Exception as e:
                    logger.debug(f"Error finding video in scripts: {e}")

            # 5. Last resort: find any video that's clearly not an ad
            if not video_url:
                try:
                    all_videos = self.driver.find_elements(By.TAG_NAME, 'video')
                    for video in all_videos:
                        if not self._is_advertisement(video):
                            # Check if the video is in the main part of the page
                            parent_text = self.driver.execute_script("""
                                var el = arguments[0];
                                var parent = el.parentElement;
                                while (parent && parent.tagName != 'BODY') {
                                    var text = (parent.innerText || '').toLowerCase();
                                    if (text.includes('ad') || text.includes('sponsored')) {
                                        return 'ad';
                                    }
                                    parent = parent.parentElement;
                                }
                                return 'clean';
                            """, video)
                            
                            if parent_text != 'ad':
                                sources = video.find_elements(By.TAG_NAME, 'source')
                                for source in sources:
                                    src = source.get_attribute('src')
                                    if src and self._is_main_video(src):
                                        video_url = src
                                        break
                                if not video_url:
                                    src = video.get_attribute('src')
                                    if src and self._is_main_video(src):
                                        video_url = src
                                if video_url:
                                    break
                except Exception as e:
                    logger.debug(f"Error in last resort video search: {e}")

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

    def _is_main_video(self, url):
        """Check if URL is a main video (not an ad or preview)"""
        if not url:
            return False
        
        # Must be video format
        if not any(ext in url.lower() for ext in ['.mp4', '.webm', '.m3u8']):
            return False
        
        # Skip obvious ad URLs
        ad_patterns = [
            'ad', 'ads', 'sponsored', 'promo', 'preroll', 'postroll',
            'adserver', 'adservice', 'doubleclick', 'googleads', 'adnxs',
            'stripchat', 'ourdream', 'sexselector', 'lustgoddess', '蓝猫',
            'banner', 'pre-roll', 'advertisement'
        ]
        
        url_lower = url.lower()
        for pattern in ad_patterns:
            if pattern in url_lower:
                logger.debug(f"Skipping ad URL: {url}")
                return False
        
        # Prefer bkcdn.net (main CDN)
        if 'bkcdn.net' in url_lower:
            return True
        
        # Allow other CDNs if they don't match ad patterns
        return True
