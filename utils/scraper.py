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
            result = self.driver.execute_script("""
                var el = arguments[0];
                var maxDepth = 6;
                while (el && maxDepth > 0) {
                    var classes = el.className || '';
                    var id = el.id || '';
                    var text = (el.innerText || '').toLowerCase();
                    var combined = (classes + ' ' + id + ' ' + text).toLowerCase();
                    
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
        """Get a unique identifier for the current page"""
        try:
            url = self.driver.current_url
            match = re.search(r'/view/(celeb|movie)/([^/]+)/?$', url)
            if match:
                return match.group(2)
            return url
        except:
            return None

    def _is_main_video(self, url):
        """Check if URL is a main video (not an ad or preview)"""
        if not url:
            return False
        
        if not any(ext in url.lower() for ext in ['.mp4', '.webm', '.m3u8']):
            return False
        
        ad_patterns = [
            'ad', 'ads', 'sponsored', 'promo', 'preroll', 'postroll',
            'adserver', 'adservice', 'doubleclick', 'googleads', 'adnxs',
            'stripchat', 'ourdream', 'sexselector', 'lustgoddess', '蓝猫',
            'banner', 'pre-roll', 'advertisement'
        ]
        
        url_lower = url.lower()
        for pattern in ad_patterns:
            if pattern in url_lower:
                return False
        
        if 'bkcdn.net' in url_lower:
            return True
        
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
            link_count = 0
            
            for link in all_links:
                link_count += 1
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip()[:50] if link.text else ''
                    
                    logger.info(f"--- Link #{link_count} ---")
                    logger.info(f"href: {href}")
                    logger.info(f"text: {text}")
                    
                    if not href:
                        logger.info("Decision: REJECTED - href is None or empty")
                        continue
                    
                    # Check if href contains /view/celeb/ or /view/movie/
                    if '/view/celeb/' in href or '/view/movie/' in href:
                        logger.info(f"Decision: ACCEPTED - matches /view/celeb/ or /view/movie/")
                        
                        if href in seen_urls:
                            logger.info("Decision: DUPLICATE - already seen")
                            continue
                        
                        # Check if link is in ad container
                        is_ad = self._is_advertisement(link)
                        if is_ad:
                            logger.info("Decision: REJECTED - in advertisement container")
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
                        
                        logger.info(f"Title extracted: {title}")
                        video_links.append({
                            'url': href,
                            'title': title[:100]
                        })
                        logger.info("-> Added to video_links")
                    else:
                        logger.info(f"Decision: REJECTED - does not match /view/celeb/ or /view/movie/")
                        
                except Exception as e:
                    logger.error(f"Error processing link #{link_count}: {e}")

            # Remove duplicates
            seen = set()
            unique_links = []
            for v in video_links:
                if v['url'] not in seen:
                    seen.add(v['url'])
                    unique_links.append(v)
            
            logger.info("=" * 60)
            logger.info("STEP 3: FINAL RESULTS")
            logger.info(f"Total video links found: {len(unique_links)}")
            for i, v in enumerate(unique_links):
                logger.info(f"  {i+1}. {v['title'][:50]} - {v['url']}")
            
            return unique_links

        except Exception as e:
            logger.error(f"Error in get_new_videos: {e}")
            return []
        finally:
            self.stop()

    def extract_video_url(self, video_page_url):
        """Extract the main video URL from a /view/ page with detailed logging"""
        logger.info("=" * 60)
        logger.info("STEP 4: EXTRACTING VIDEO FROM PAGE")
        logger.info(f"Processing page: {video_page_url}")
        
        self.start()
        try:
            self.driver.get(video_page_url)
            logger.info(f"Page loaded. Current URL: {self.driver.current_url}")
            
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(5)
            
            logger.info("Scrolling to load lazy content...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            page_id = self._get_page_identifier()
            logger.info(f"Page identifier: {page_id}")

            logger.info("=" * 60)
            logger.info("STEP 5: FINDING VIDEO ELEMENTS")
            
            all_videos = self.driver.find_elements(By.TAG_NAME, 'video')
            logger.info(f"Total video elements found: {len(all_videos)}")

            if len(all_videos) == 0:
                logger.warning("No video elements found on page")
                logger.info("Attempting HTML source extraction as fallback...")
                video_url = self._extract_video_from_html()
                if video_url:
                    logger.info(f"Found video via HTML fallback: {video_url}")
                return video_url

            candidates = []
            
            for idx, video in enumerate(all_videos):
                logger.info(f"--- Candidate Video #{idx+1} ---")
                
                # Get parent info
                parent_info = self.driver.execute_script("""
                    var el = arguments[0];
                    var info = {
                        tag: el.tagName,
                        classes: el.className || '',
                        id: el.id || '',
                        parentTag: '',
                        parentClasses: '',
                        parentId: '',
                        parentText: ''
                    };
                    if (el.parentElement) {
                        info.parentTag = el.parentElement.tagName;
                        info.parentClasses = el.parentElement.className || '';
                        info.parentId = el.parentElement.id || '';
                        info.parentText = (el.parentElement.innerText || '').substring(0, 200);
                    }
                    return info;
                """, video)
                
                logger.info(f"Video classes: {parent_info['classes']}")
                logger.info(f"Video id: {parent_info['id']}")
                logger.info(f"Parent tag: {parent_info['parentTag']}")
                logger.info(f"Parent classes: {parent_info['parentClasses']}")
                logger.info(f"Parent id: {parent_info['parentId']}")
                
                # Check if this is an ad
                is_ad = self._is_advertisement(video)
                logger.info(f"Is advertisement: {is_ad}")
                
                # Get sources
                sources = video.find_elements(By.TAG_NAME, 'source')
                srcs = []
                for source in sources:
                    src = source.get_attribute('src')
                    if src:
                        srcs.append(src)
                        logger.info(f"  Source URL: {src}")
                
                video_src = video.get_attribute('src')
                if video_src:
                    srcs.append(video_src)
                    logger.info(f"  Video src attribute: {video_src}")
                
                logger.info(f"Total source URLs found: {len(srcs)}")
                
                # Score this video
                score = 0
                score_details = []
                
                valid_sources = [s for s in srcs if self._is_main_video(s)]
                if valid_sources:
                    score += 10
                    score_details.append(f"Has {len(valid_sources)} valid sources")
                    for s in valid_sources:
                        logger.info(f"  Valid source: {s}")
                
                if not is_ad:
                    score += 20
                    score_details.append("Not in ad container")
                
                if page_id:
                    try:
                        parent_text = self.driver.execute_script("""
                            var el = arguments[0];
                            var parent = el.parentElement;
                            while (parent && parent.tagName != 'BODY') {
                                if ((parent.innerText || '').includes(arguments[1])) {
                                    return true;
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                        """, video, page_id)
                        if parent_text:
                            score += 30
                            score_details.append(f"Parent contains page identifier: {page_id}")
                        else:
                            logger.info(f"Parent does NOT contain page identifier: {page_id}")
                    except Exception as e:
                        logger.error(f"Error checking parent text: {e}")
                
                # Check if in main content
                try:
                    in_main = self.driver.execute_script("""
                        var el = arguments[0];
                        var parent = el.parentElement;
                        while (parent && parent.tagName != 'BODY') {
                            var tag = parent.tagName.toLowerCase();
                            if (tag === 'main' || tag === 'article' || 
                                parent.className.includes('content') || 
                                parent.className.includes('scene') ||
                                parent.className.includes('player')) {
                                return true;
                            }
                            parent = parent.parentElement;
                        }
                        return false;
                    """, video)
                    if in_main:
                        score += 25
                        score_details.append("In main content area")
                    else:
                        logger.info("Not in main content area")
                except Exception as e:
                    logger.error(f"Error checking main content: {e}")
                
                has_main_cdn = any('bkcdn.net' in s for s in srcs)
                if has_main_cdn:
                    score += 15
                    score_details.append("Has bkcdn.net URL")
                else:
                    logger.info("No bkcdn.net URL found")
                
                logger.info(f"TOTAL SCORE: {score}")
                logger.info(f"Score details: {', '.join(score_details)}")
                
                candidates.append({
                    'video': video,
                    'srcs': srcs,
                    'score': score,
                    'is_ad': is_ad,
                    'details': score_details
                })

            # Sort by score
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info("=" * 60)
            logger.info("STEP 6: SELECTING BEST CANDIDATE")
            
            video_url = None
            selected_candidate = None
            
            for i, candidate in enumerate(candidates):
                logger.info(f"--- Candidate #{i+1} (Score: {candidate['score']}) ---")
                
                if candidate['score'] < 20:
                    logger.info(f"REJECTED: Score below threshold (20)")
                    continue
                
                for src in candidate['srcs']:
                    if self._is_main_video(src):
                        video_url = src
                        selected_candidate = candidate
                        logger.info(f"ACCEPTED: {src}")
                        break
                
                if video_url:
                    break
                else:
                    logger.info("REJECTED: No valid source URL found")

            if selected_candidate:
                logger.info("=" * 60)
                logger.info("STEP 7: SELECTION COMPLETE")
                logger.info(f"Selected candidate score: {selected_candidate['score']}")
                logger.info(f"Selected candidate details: {', '.join(selected_candidate['details'])}")
                logger.info(f"Selected video URL: {video_url}")
            else:
                logger.warning("No suitable candidate found with score >= 20")

            # Final fallback
            if not video_url:
                logger.info("No candidate selected. Attempting HTML source extraction as fallback...")
                video_url = self._extract_video_from_html()
                if video_url:
                    logger.info(f"Found video via HTML fallback: {video_url}")

            logger.info("=" * 60)
            logger.info("FINAL RESULT")
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

    def _extract_video_from_html(self):
        """Extract video URL from HTML source as fallback"""
        try:
            page_source = self.driver.page_source
            logger.info("Parsing HTML source for video URLs...")
            
            patterns = [
                r'https?://[^\s"\']+\.(?:mp4|webm|m3u8)',
                r'data-video="([^"]+)"',
                r'data-src="([^"]+)"',
                r'src="([^"]+\.(?:mp4|webm|m3u8))"',
                r'videoUrl\s*[:=]\s*["\']([^"\']+)["\']',
                r'file\s*[:=]\s*["\']([^"\']+)["\']',
                r'source\s*[:=]\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_source)
                if matches:
                    logger.info(f"Pattern {pattern} found {len(matches)} matches")
                    for match in matches:
                        if self._is_main_video(match):
                            logger.info(f"Found valid video in HTML: {match}")
                            return match
        except Exception as e:
            logger.error(f"Error in HTML extraction: {e}")
        return None
