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
        """Check if an element is inside a real advertisement container"""
        try:
            result = self.driver.execute_script("""
                var el = arguments[0];
                var maxDepth = 4;
                while (el && maxDepth > 0) {
                    var classes = el.className || '';
                    var id = el.id || '';
                    
                    // Only reject if element is inside a known ad container
                    var adClassPatterns = [
                        'ad-container', 'ad-wrapper', 'sponsored-post', 
                        'promo-box', 'banner-ad', 'advertisement',
                        'stripchat-ad', 'ourdream-ad'
                    ];
                    for (var i = 0; i < adClassPatterns.length; i++) {
                        if (classes.includes(adClassPatterns[i]) || 
                            id.includes(adClassPatterns[i])) {
                            return true;
                        }
                    }
                    
                    // Check for specific ad service text (exact matches)
                    var text = (el.innerText || '').toLowerCase();
                    var exactAdText = ['stripchat', 'ourdream.ai', 'sexselector', 
                                      'lustgoddess', '蓝猫', 'your fantasy'];
                    for (var i = 0; i < exactAdText.length; i++) {
                        if (text.includes(exactAdText[i])) {
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

    def get_new_videos(self, url):
        """Get video links from the recent page with detailed logging"""
        logger.info("=" * 60)
        logger.info("STEP 1: LOADING RECENT PAGE")
        logger.info(f"Target URL: {url}")
        
        self.start()
        try:
            self.driver.get(url)
            logger.info(f"Page loaded. Current URL: {self.driver.current_url}")
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)

            logger.info("=" * 60)
            logger.info("STEP 2: EXTRACTING ALL LINKS")
            
            all_links = self.driver.find_elements(By.TAG_NAME, 'a')
            logger.info(f"Total links found: {len(all_links)}")

            video_links = []
            seen_urls = set()
            accepted_count = 0
            rejected_count = 0
            
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip()[:50] if link.text else ''
                    
                    if not href:
                        continue
                    
                    # Check if href contains /view/celeb/ or /view/movie/
                    if '/view/celeb/' in href or '/view/movie/' in href:
                        if href in seen_urls:
                            continue
                        
                        # Check if link is in ad container
                        is_ad = self._is_advertisement(link)
                        if is_ad:
                            logger.info(f"REJECTED (advertisement): {href} - {text}")
                            rejected_count += 1
                            continue
                        
                        seen_urls.add(href)
                        accepted_count += 1
                        
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
                        
                        logger.info(f"ACCEPTED: {href} - {title[:50]}")
                        video_links.append({
                            'url': href,
                            'title': title[:100]
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing link: {e}")

            # Remove duplicates
            seen = set()
            unique_links = []
            for v in video_links:
                if v['url'] not in seen:
                    seen.add(v['url'])
                    unique_links.append(v)
            
            logger.info("=" * 60)
            logger.info("STEP 3: FINAL RESULTS")
            logger.info(f"Accepted: {accepted_count}, Rejected (ad): {rejected_count}")
            logger.info(f"Total unique video links: {len(unique_links)}")
            for i, v in enumerate(unique_links):
                logger.info(f"  {i+1}. {v['title'][:50]} - {v['url']}")
            
            return unique_links

        except Exception as e:
            logger.error(f"Error in get_new_videos: {e}")
            return []
        finally:
            self.stop()

    def extract_video_url(self, video_page_url):
        """Placeholder - will be fixed in next stage"""
        logger.info(f"Processing page: {video_page_url}")
        return None
