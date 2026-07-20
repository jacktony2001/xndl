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
        """Extract the main video URL from a /view/ page with multi-signal scoring"""
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
            
            # Scroll to load lazy content
            logger.info("Scrolling to load lazy content...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            # Get page identifier
            page_id = None
            try:
                url = self.driver.current_url
                match = re.search(r'/view/(celeb|movie)/([^/]+)/?$', url)
                if match:
                    page_id = match.group(2)
                else:
                    page_id = url
                logger.info(f"Page identifier: {page_id}")
            except:
                page_id = video_page_url
                logger.info(f"Page identifier (fallback): {page_id}")

            # Get page title
            page_title = ""
            try:
                page_title = self.driver.find_element(By.TAG_NAME, 'h1').text.strip()
                logger.info(f"Page h1 title: {page_title}")
            except:
                logger.info("Page h1 title: Not found")

            logger.info("=" * 60)
            logger.info("STEP 5: FINDING VIDEO ELEMENTS")
            
            all_videos = self.driver.find_elements(By.TAG_NAME, 'video')
            logger.info(f"Total video elements found: {len(all_videos)}")

            if len(all_videos) == 0:
                logger.warning("No video elements found on page")
                logger.info("Attempting HTML source extraction as fallback...")
                video_url = self._extract_video_from_html(page_id, page_title)
                if video_url:
                    logger.info(f"Found video via HTML fallback: {video_url}")
                return video_url

            candidates = []
            
            for idx, video in enumerate(all_videos):
                logger.info(f"--- Candidate Video #{idx+1} ---")

                # ❌ رد کردن ویدیوهای تبلیغاتی و widget کناری
                is_ad_video = self.driver.execute_script("""
                    var el = arguments[0];
                    var parent = el.parentElement;
                    var depth = 0;
                    while (parent && depth < 6) {
                        var classes = (parent.className || '').toLowerCase();
                        if (classes.includes('exo-native-widget') ||
                            classes.includes('video-thumb-wrapper') ||
                            /group-container-placement-\d/.test(classes)) {
                            return true;
                        }
                        parent = parent.parentElement;
                        depth++;
                    }
                    return false;
                """, video)
                if is_ad_video:
                    logger.info(f"  ⏭️ Skip: ویدیوی تبلیغاتی/widget")
                    continue

                # Get element info
                element_info = self.driver.execute_script("""
                    var el = arguments[0];
                    var info = {
                        tag: el.tagName,
                        classes: el.className || '',
                        id: el.id || '',
                        width: el.getAttribute('width') || '',
                        height: el.getAttribute('height') || '',
                        poster: el.getAttribute('poster') || '',
                        parentTag: '',
                        parentClasses: '',
                        parentId: '',
                        parentText: '',
                        grandparentTag: '',
                        grandparentClasses: ''
                    };
                    if (el.parentElement) {
                        info.parentTag = el.parentElement.tagName;
                        info.parentClasses = el.parentElement.className || '';
                        info.parentId = el.parentElement.id || '';
                        info.parentText = (el.parentElement.innerText || '').substring(0, 300);
                        if (el.parentElement.parentElement) {
                            info.grandparentTag = el.parentElement.parentElement.tagName;
                            info.grandparentClasses = el.parentElement.parentElement.className || '';
                        }
                    }
                    return info;
                """, video)
                
                logger.info(f"Video classes: {element_info['classes']}")
                logger.info(f"Video id: {element_info['id']}")
                logger.info(f"Video dimensions: {element_info['width']}x{element_info['height']}")
                logger.info(f"Parent tag: {element_info['parentTag']}")
                logger.info(f"Parent classes: {element_info['parentClasses']}")
                logger.info(f"Grandparent tag: {element_info['grandparentTag']}")
                logger.info(f"Grandparent classes: {element_info['grandparentClasses']}")
                
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
                
                # SCORING SYSTEM - Multiple signals
                score = 0
                score_details = []
                valid_sources = []
                
                # Signal 1: Valid sources (not ads, video format)
                for s in srcs:
                    if self._is_main_video(s):
                        valid_sources.append(s)
                        logger.info(f"  ✓ Valid source: {s}")
                    else:
                        logger.info(f"  ✗ Invalid source: {s}")
                
                if valid_sources:
                    score += 15
                    score_details.append(f"Valid sources: {len(valid_sources)}")
                
                # Signal 2: Not an ad container
                is_ad = self._is_advertisement(video)
                if not is_ad:
                    score += 20
                    score_details.append("Not in ad container")
                else:
                    logger.info("REJECTED: In ad container")
                    continue
                
                # Signal 3: Page title/identifier in parent or grandparent
                if page_id or page_title:
                    try:
                        has_page_context = self.driver.execute_script("""
                            var el = arguments[0];
                            var page_id = arguments[1];
                            var page_title = arguments[2];
                            var parent = el.parentElement;
                            var context = '';
                            var depth = 0;
                            while (parent && depth < 3) {
                                context += (parent.innerText || '') + ' ';
                                depth++;
                                parent = parent.parentElement;
                            }
                            context = context.toLowerCase();
                            if (page_id && context.includes(page_id.toLowerCase())) {
                                return 2;
                            }
                            if (page_title && context.includes(page_title.toLowerCase())) {
                                return 1;
                            }
                            return 0;
                        """, video, page_id, page_title)
                        
                        if has_page_context == 2:
                            score += 35
                            score_details.append("Parent contains page ID")
                            logger.info("  ✓ Parent contains page ID")
                        elif has_page_context == 1:
                            score += 20
                            score_details.append("Parent contains page title")
                            logger.info("  ✓ Parent contains page title")
                        else:
                            logger.info("  ✗ No page context found in parent")
                    except Exception as e:
                        logger.error(f"Error checking page context: {e}")
                
                # Signal 4: In main content area
                try:
                    in_main = self.driver.execute_script("""
                        var el = arguments[0];
                        var parent = el.parentElement;
                        while (parent && parent.tagName != 'BODY') {
                            var tag = parent.tagName.toLowerCase();
                            var classes = (parent.className || '').toLowerCase();
                            if (tag === 'main' || tag === 'article' || 
                                classes.includes('content') || 
                                classes.includes('scene') ||
                                classes.includes('player') ||
                                classes.includes('video-wrapper')) {
                                return true;
                            }
                            parent = parent.parentElement;
                        }
                        return false;
                    """, video)
                    
                    if in_main:
                        score += 25
                        score_details.append("In main content area")
                        logger.info("  ✓ In main content area")
                    else:
                        logger.info("  ✗ Not in main content area")
                except Exception as e:
                    logger.error(f"Error checking main content: {e}")
                
                # Signal 5: Uses bkcdn.net (main CDN)
                has_main_cdn = any('bkcdn.net' in s for s in srcs)
                if has_main_cdn:
                    score += 15
                    score_details.append("Uses main CDN (bkcdn.net)")
                    logger.info("  ✓ Uses main CDN")
                else:
                    logger.info("  ✗ Not using main CDN")
                
                # Signal 6: Video has poster attribute (indicates actual video)
                if element_info['poster']:
                    score += 10
                    score_details.append("Has poster attribute")
                    logger.info("  ✓ Has poster attribute")
                
                # Signal 7: Video dimensions are reasonable
                try:
                    width = int(element_info['width']) if element_info['width'] else 0
                    height = int(element_info['height']) if element_info['height'] else 0
                    if width > 200 and height > 200:
                        score += 10
                        score_details.append(f"Reasonable dimensions: {width}x{height}")
                        logger.info(f"  ✓ Reasonable dimensions: {width}x{height}")
                    else:
                        logger.info(f"  ✗ Small dimensions: {width}x{height}")
                except:
                    pass
                
                logger.info(f"TOTAL SCORE: {score}")
                logger.info(f"Score details: {', '.join(score_details) if score_details else 'No positive indicators'}")
                
                candidates.append({
                    'video': video,
                    'srcs': srcs,
                    'valid_sources': valid_sources,
                    'score': score,
                    'details': score_details,
                    'element_info': element_info,
                    'is_ad': is_ad
                })

            # Sort by score descending
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info("=" * 60)
            logger.info("STEP 6: CANDIDATE COMPARISON")
            
            # Log all candidates with their scores
            logger.info("All candidates (sorted by score):")
            for i, c in enumerate(candidates):
                logger.info(f"  #{i+1}: Score={c['score']} | Details: {', '.join(c['details']) if c['details'] else 'None'}")
                if c['valid_sources']:
                    logger.info(f"       Sources: {c['valid_sources'][0][:80]}...")
            
            # Select best candidate
            video_url = None
            selected_candidate = None
            
            if not candidates:
                logger.warning("No candidates available")
            else:
                # Get best candidate
                best = candidates[0]
                logger.info(f"Best candidate score: {best['score']}")
                
                # Threshold: need at least 30 points to be considered valid
                if best['score'] >= 30:
                    for src in best['valid_sources']:
                        if self._is_main_video(src):
                            video_url = src
                            selected_candidate = best
                            logger.info(f"ACCEPTED: Selected candidate #1 with score {best['score']}")
                            break
                else:
                    logger.warning(f"REJECTED: Best candidate score {best['score']} is below threshold (30)")
                    
                    # Check if any other candidate meets threshold
                    for i, c in enumerate(candidates[1:], start=2):
                        if c['score'] >= 30:
                            for src in c['valid_sources']:
                                if self._is_main_video(src):
                                    video_url = src
                                    selected_candidate = c
                                    logger.info(f"ACCEPTED: Selected candidate #{i} with score {c['score']}")
                                    break
                            if video_url:
                                break

            if selected_candidate:
                logger.info("=" * 60)
                logger.info("STEP 7: SELECTION COMPLETE")
                logger.info(f"Selected candidate score: {selected_candidate['score']}")
                logger.info(f"Selected candidate details: {', '.join(selected_candidate['details'])}")
                logger.info(f"Selected video URL: {video_url}")
            else:
                logger.warning("=" * 60)
                logger.warning("No suitable candidate found (all below threshold or no valid sources)")
                logger.warning(f"Best available score: {candidates[0]['score'] if candidates else 'N/A'}")

            # Final fallback: HTML source extraction with validation
            if not video_url:
                logger.info("No candidate selected. Attempting HTML source extraction with validation...")
                video_url = self._extract_video_from_html(page_id, page_title)
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

    def _extract_video_from_html(self, page_id=None, page_title=None):
        """Extract video URL from HTML source with validation"""
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
            
            candidates_found = []
            
            for pattern in patterns:
                matches = re.findall(pattern, page_source)
                if matches:
                    logger.info(f"Pattern {pattern} found {len(matches)} matches")
                    for match in matches:
                        if self._is_main_video(match):
                            # Calculate context score
                            context_score = 0
                            if page_id and page_id in page_source:
                                context_score += 20
                            if page_title and page_title in page_source:
                                context_score += 15
                            if 'bkcdn.net' in match:
                                context_score += 10
                            
                            candidates_found.append({
                                'url': match,
                                'score': context_score,
                                'details': []
                            })
            
            if candidates_found:
                # Sort by score and pick best
                candidates_found.sort(key=lambda x: x['score'], reverse=True)
                best = candidates_found[0]
                logger.info(f"HTML fallback candidates: {len(candidates_found)}")
                for i, c in enumerate(candidates_found):
                    logger.info(f"  #{i+1}: Score={c['score']} | URL: {c['url'][:80]}...")
                
                if best['score'] >= 20:  # Minimum threshold for HTML fallback
                    logger.info(f"Selected HTML fallback: {best['url']}")
                    return best['url']
                else:
                    logger.warning(f"Best HTML candidate score {best['score']} is below threshold")
            
            return None
        except Exception as e:
            logger.error(f"Error in HTML extraction: {e}")
            return None
