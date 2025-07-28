#!/usr/bin/env python3
"""Test to map Facebook Page IDs to page information using Playwright.

This test extracts unique Page IDs from comment data files and uses Playwright
to scrape page information directly from Facebook URLs. Uses concurrent processing
for dramatically faster execution with detailed timing metrics.

Results are stored in data/facebook/pages-{timestamp}.json.

Usage:
    python tests/test_page_mapping.py                    # Default: 3 concurrent, headless, with about pages
    python tests/test_page_mapping.py --concurrent 5     # Use 5 concurrent browser contexts
    python tests/test_page_mapping.py --no-headless      # Run with visible browser UI
    python tests/test_page_mapping.py --no-about         # Skip about page scraping for speed
"""

import argparse
import json
import sys
import asyncio
import time
from typing import Dict, Any, Optional, Set, List
from pathlib import Path
from datetime import datetime
import glob
import re
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from higherdose.utils.style import ansi
from higherdose.utils.logs import report

logger = report.settings(__file__)


def extract_page_ids_from_posts(post_ids: List[str]) -> Set[str]:
    """Extract unique Page IDs from Post IDs in PageID_PostID format."""
    page_ids = set()
    for post_id in post_ids:
        if "_" in post_id:
            page_id = post_id.split("_")[0]
            page_ids.add(page_id)
        else:
            logger.warning("Post ID doesn't follow PageID_PostID format: %s", post_id)
    return page_ids


def extract_page_ids_from_comment_files(data_dir: str = "data/facebook") -> Set[str]:
    """Extract all unique Page IDs from comment JSON files."""
    page_ids = set()
    comment_files = glob.glob(f"{data_dir}/comments-*.json")

    if not comment_files:
        print(f"{ansi.yellow}No comment files found in {data_dir}{ansi.reset}")
        return page_ids

    print(f"Found {len(comment_files)} comment file(s) to process:")

    for file_path in comment_files:
        print(f"  Processing: {ansi.cyan}{Path(file_path).name}{ansi.reset}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract from ad_to_posts mapping
            if "ad_to_posts" in data:
                for post_list in data["ad_to_posts"].values():
                    if isinstance(post_list, list):
                        page_ids.update(extract_page_ids_from_posts(post_list))
                    else:
                        # Handle case where it might be a single string
                        page_ids.update(extract_page_ids_from_posts([post_list]))

            # Extract from ad_to_post mapping (single post per ad)
            if "ad_to_post" in data:
                post_ids = list(data["ad_to_post"].values())
                page_ids.update(extract_page_ids_from_posts(post_ids))

            # Extract from any other post ID fields that might exist
            if "posts" in data:
                post_ids = []
                for post_data in data["posts"].values():
                    if "post_id" in post_data:
                        post_ids.append(post_data["post_id"])
                page_ids.update(extract_page_ids_from_posts(post_ids))

        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            print(f"    {ansi.red}Error processing {file_path}: {e}{ansi.reset}")
            logger.error("Error processing %s: %s", file_path, e)

    print(f"Extracted {ansi.yellow}{len(page_ids)}{ansi.reset} unique Page IDs")
    return page_ids


def count_posts_per_page(data_dir: str = "data/facebook") -> Dict[str, int]:
    """Count how many posts each page has across all comment files."""
    page_post_counts = {}
    comment_files = glob.glob(f"{data_dir}/comments-*.json")

    for file_path in comment_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Count from ad_to_posts mapping
            if "ad_to_posts" in data:
                for post_list in data["ad_to_posts"].values():
                    if isinstance(post_list, list):
                        for post_id in post_list:
                            if "_" in post_id:
                                page_id = post_id.split("_")[0]
                                page_post_counts[page_id] = page_post_counts.get(page_id, 0) + 1
                    else:
                        if "_" in post_list:
                            page_id = post_list.split("_")[0]
                            page_post_counts[page_id] = page_post_counts.get(page_id, 0) + 1

            # Count from ad_to_post mapping
            if "ad_to_post" in data:
                for post_id in data["ad_to_post"].values():
                    if "_" in post_id:
                        page_id = post_id.split("_")[0]
                        page_post_counts[page_id] = page_post_counts.get(page_id, 0) + 1

        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.error("Error counting posts in %s: %s", file_path, e)

    return page_post_counts


class FacebookPageScraper:
    """Playwright-based Facebook page scraper."""

    def __init__(self):
        """Initialize empty Playwright browser, context, and page placeholders."""
        self.browser: Optional[any] = None
        self.context: Optional[any] = None
        self.page: Optional[any] = None

    async def start(self, headless: bool = True):
        """Launch a Chromium browser and warm-up a single page.

        Parameters
        ----------
        headless : bool, default ``True``
            Run the browser in headless mode. Pass ``--no-headless`` on the CLI
            to open a visible window for debugging.
        """
        playwright = await async_playwright().start()

        # Launch browser with realistic user agent
        self.browser = await playwright.chromium.launch(
            headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        self.page = await self.context.new_page()

        # Set up some realistic headers and behavior
        await self.page.set_extra_http_headers(
            {
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )

        logger.info("Playwright browser started successfully")

    async def close(self):
        """Close Playwright browser, context, and page (if they exist)."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            # Add a small delay to allow subprocess cleanup on Windows
            await asyncio.sleep(0.1)
        except (PlaywrightError, AttributeError) as e:
            # Ignore cleanup errors - they're not critical
            logger.debug("Error during browser cleanup: %s", e)

    async def scrape_facebook_page(self, page_id: str, force_about: bool = False) -> Dict[str, Any]:
        """Scrape Facebook page information using Playwright."""
        start_time = time.perf_counter()
        url = f"https://www.facebook.com/{page_id}"

        page_data = {
            "page_id": page_id,
            "url_original": url,
            "scrape_timestamp": datetime.now().isoformat(),
            "scrape_success": False,
        }

        try:
            logger.info("Scraping Facebook page: %s", page_id)

            # Navigate to the page
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)

            if not response or response.status >= 400:
                page_data["error"] = f"HTTP {response.status if response else 'timeout'}"
                duration = time.perf_counter() - start_time
                page_data["scrape_duration_seconds"] = round(duration, 2)
                logger.warning(
                    "Page %s failed in %.2f seconds: %s",
                    page_id,
                    duration,
                    page_data["error"],
                )
                return page_data

            # Reduced wait time for faster processing
            await self.page.wait_for_timeout(1000)  # Reduced from 2000ms to 1000ms

            # Get final URL after any redirects (e.g., page ID -> username)
            final_url = self.page.url
            page_data["url_final"] = final_url

            # Extract username from final URL if it changed
            if final_url != url:
                username_match = re.search(r"facebook\.com/([^/?]+)", final_url)
                if username_match:
                    page_data["username"] = username_match.group(1)

            # Extract page title
            title = await self.page.title()
            page_data["page_title"] = title

            # Try to extract page name from title (remove " | Facebook" suffix)
            if title:
                clean_name = re.sub(r"\s*[\|\-]\s*Facebook.*$", "", title, flags=re.IGNORECASE)
                if clean_name and clean_name != title:
                    page_data["name"] = clean_name.strip()

            # Try to extract page name from h1 or other selectors
            name_selectors = [
                'h1[data-testid="page_title"]',
                "h1.x1heor9g",  # Facebook's class for page titles
                "h1:first-of-type",
                '[role="main"] h1',
                ".x1e56ztr span",  # Alternative page name selector
            ]

            for selector in name_selectors:
                try:
                    name_element = await self.page.query_selector(selector)
                    if name_element:
                        name_text = await name_element.text_content()
                        if name_text and name_text.strip():
                            page_data["name"] = name_text.strip()
                            break
                except PlaywrightError:
                    continue

            # Try to extract category
            category_selectors = [
                '[data-testid="page_category"]',
                '.x1i10hfl[role="button"]:has-text("Category")',
                'span:has-text("Category") + span',
                '.x1lliihq:has-text("·")',  # Often categories are after a bullet point
            ]

            for selector in category_selectors:
                try:
                    category_element = await self.page.query_selector(selector)
                    if category_element:
                        category_text = await category_element.text_content()
                        if category_text and category_text.strip():
                            page_data["category"] = category_text.strip()
                            break
                except PlaywrightError:
                    continue

            # Try to extract description/about
            description_selectors = [
                '[data-testid="page_description"]',
                ".x1pha0wt .x1lliihq",  # Common description area
                '[role="main"] .x1lliihq:not(h1)',
                ".x1e56ztr .x1lliihq",
            ]

            for selector in description_selectors:
                try:
                    desc_element = await self.page.query_selector(selector)
                    if desc_element:
                        desc_text = await desc_element.text_content()
                        if (
                            desc_text and len(desc_text.strip()) > 20
                        ):  # Reasonable length for description
                            page_data["description"] = desc_text.strip()
                            break
                except PlaywrightError:
                    continue

            # Try to extract follower count
            follower_patterns = [
                r"([\d,]+)\s+(?:followers?|likes?)",
                r"([\d,]+)\s+people like this",
                r"([\d,]+)\s+people follow this",
            ]

            page_content = await self.page.content()
            for pattern in follower_patterns:
                match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    try:
                        follower_count = int(match.group(1).replace(",", ""))
                        page_data["follower_count"] = follower_count
                        break
                    except ValueError:
                        continue

            # Check if page is verified (blue checkmark)
            try:
                verified_element = await self.page.query_selector('[aria-label*="Verified"]')
                page_data["verified"] = verified_element is not None
            except PlaywrightError:
                page_data["verified"] = False

            # Check if page is accessible (not private/restricted)
            page_content_lower = page_content.lower()
            if any(
                phrase in page_content_lower
                for phrase in [
                    "content isn't available",
                    "page isn't available",
                    "sorry, this content isn't available",
                    "this page isn't available",
                ]
            ):
                page_data["accessible"] = False
                page_data["error"] = "Page not accessible or private"
                duration = time.perf_counter() - start_time
                page_data["scrape_duration_seconds"] = round(duration, 2)
                logger.warning("Page %s not accessible (%.2f seconds)", page_id, duration)
                return page_data
            else:
                page_data["accessible"] = True
                page_data["scrape_success"] = True

            # If description is missing or too short, try the /about/ page
            # BUT only if force_about is True (respect --no-about flag completely)
            current_description = page_data.get("description", "")
            if force_about and (not current_description or len(current_description) < 50):
                about_start = time.perf_counter()
                about_data = await self.scrape_about_page(page_id, page_data.get("username"))
                about_duration = time.perf_counter() - about_start

                if about_data:
                    # Merge about page data
                    page_data.update(about_data)
                    page_data["about_page_scraped"] = True
                    page_data["about_scrape_duration_seconds"] = round(about_duration, 2)
                    logger.info(
                        "About page for %s scraped in %.2f seconds",
                        page_id,
                        about_duration,
                    )
                else:
                    page_data["about_page_scraped"] = False
                    page_data["about_scrape_duration_seconds"] = round(about_duration, 2)
            elif force_about:
                # Force about page even if description exists
                about_start = time.perf_counter()
                about_data = await self.scrape_about_page(page_id, page_data.get("username"))
                about_duration = time.perf_counter() - about_start

                if about_data:
                    # Merge about page data
                    page_data.update(about_data)
                    page_data["about_page_scraped"] = True
                    page_data["about_scrape_duration_seconds"] = round(about_duration, 2)
                    logger.info(
                        "About page for %s scraped in %.2f seconds",
                        page_id,
                        about_duration,
                    )
                else:
                    page_data["about_page_scraped"] = False
                    page_data["about_scrape_duration_seconds"] = round(about_duration, 2)
            else:
                # --no-about specified: skip about page completely
                page_data["about_page_scraped"] = False
                logger.info("About page scraping skipped for %s (--no-about specified)", page_id)

            duration = time.perf_counter() - start_time
            page_data["scrape_duration_seconds"] = round(duration, 2)
            logger.info("Page %s scraped successfully in %.2f seconds", page_id, duration)
            return page_data

        except (PlaywrightError, PlaywrightTimeoutError, ValueError) as e:
            duration = time.perf_counter() - start_time
            logger.error(
                "Error scraping page %s after %.2f seconds: %s",
                page_id,
                duration,
                str(e),
            )
            page_data["error"] = str(e)
            page_data["accessible"] = False
            page_data["scrape_duration_seconds"] = round(duration, 2)
            return page_data

    async def scrape_about_page(
        self, page_id: str, username: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Scrape additional information from the Facebook page's /about/ section."""
        about_data = {}

        # Try different about page URL formats
        about_urls = []
        if username and username != "people":
            about_urls.append(f"https://www.facebook.com/{username}/about/")
        about_urls.append(f"https://www.facebook.com/pg/{page_id}/about/")
        about_urls.append(f"https://www.facebook.com/{page_id}/about/")

        for about_url in about_urls:
            try:
                logger.info("Trying about page: %s", about_url)
                response = await self.page.goto(
                    about_url, wait_until="domcontentloaded", timeout=8000
                )  # Reduced from 10000ms

                if not response or response.status >= 400:
                    continue

                # Reduced wait for content to load
                await self.page.wait_for_timeout(1000)  # Reduced from 2000ms

                # Extract description/bio from about page
                about_selectors = [
                    '[data-testid="about_page_description"]',
                    ".x1pha0wt .x1lliihq",
                    '[role="main"] .x1lliihq',
                    ".x78zum5 .x1lliihq",
                    'div[dir="auto"] span',
                    ".x1e56ztr .x193iq5w",
                ]

                for selector in about_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        for element in elements:
                            text = await element.text_content()
                            if text and len(text.strip()) > 30:  # Substantial description
                                # Skip if it's just navigation or page name
                                if any(
                                    skip_phrase in text.lower()
                                    for skip_phrase in [
                                        "about",
                                        "posts",
                                        "photos",
                                        "videos",
                                        "events",
                                        "community",
                                        "see all",
                                        "more",
                                        "facebook",
                                        "follow",
                                        "message",
                                    ]
                                ):
                                    continue
                                about_data["about_description"] = text.strip()
                                break
                        if "about_description" in about_data:
                            break
                    except PlaywrightError:
                        continue

                # Extract website/contact info
                external_websites = []
                social_media_links = []

                # Look for external links with better filtering
                link_selectors = [
                    'a[href^="http"]:not([href*="facebook.com"])',  # External HTTP/HTTPS links, not Facebook
                    'a[href^="https://"]:not([href*="facebook.com"])',  # HTTPS links specifically
                    'a[href^="www."]:not([href*="facebook.com"])',  # www links
                    '[data-testid="about_contact_info"] a[href^="http"]',  # Contact info links
                    '.x1i10hfl[role="link"][href^="http"]:not([href*="facebook.com"])',  # External role links
                    'a[rel="noopener"]',  # Often used for external business links
                    'a[target="_blank"]:not([href*="facebook.com"])',  # External links opening in new tab
                ]

                for selector in link_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        for element in elements:
                            href = await element.get_attribute("href")
                            text = await element.text_content()

                            if not href:
                                continue

                            # Clean up the URL
                            if href.startswith("www."):
                                href = f"https://{href}"

                            # Skip Facebook internal links
                            facebook_internal_patterns = [
                                "facebook.com/",
                                "/reel/",
                                "/watch/",
                                "/photo",
                                "/posts/",
                                "/events/",
                                "/photos/",
                                "/videos/",
                                "fb.com/",
                                "m.facebook.com",
                                # Facebook internal relative URLs
                                "/privacy/",
                                "/policies/",
                                "/business/",
                                "/help/",
                                "/stories/",
                                "/terms/",
                                "/legal/",
                                "/careers/",
                                "/about/",
                                "/safety/",
                                "/developers/",
                                "/support/",
                            ]

                            # Also skip if it's a relative URL starting with / (likely Facebook internal)
                            if href.startswith("/") and not href.startswith("//"):
                                continue

                            if any(
                                pattern in href.lower() for pattern in facebook_internal_patterns
                            ):
                                continue

                            # Categorize social media vs business websites
                            social_media_domains = [
                                "instagram.com",
                                "twitter.com",
                                "x.com",
                                "linkedin.com",
                                "youtube.com",
                                "tiktok.com",
                                "pinterest.com",
                                "snapchat.com",
                            ]

                            is_social_media = any(
                                domain in href.lower() for domain in social_media_domains
                            )

                            # Create link entry
                            link_entry = {
                                "url": href,
                                "text": text.strip() if text else href,
                                "domain": self._extract_domain(href),
                            }

                            # Avoid duplicates
                            existing_urls = [
                                link["url"] for link in external_websites + social_media_links
                            ]
                            if href not in existing_urls:
                                if is_social_media:
                                    social_media_links.append(link_entry)
                                else:
                                    external_websites.append(link_entry)
                    except PlaywrightError:
                        continue

                # Store the filtered results
                if external_websites:
                    about_data["external_websites"] = external_websites

                if social_media_links:
                    about_data["social_media_links"] = social_media_links

                # Extract business hours if present
                try:
                    hours_elements = await self.page.query_selector_all(
                        'text[contains(., "Mon")] | text[contains(., "Hours")]'
                    )
                    hours_text = []
                    for element in hours_elements:
                        text = await element.text_content()
                        if text and any(
                            day in text for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                        ):
                            hours_text.append(text.strip())

                    if hours_text:
                        about_data["business_hours"] = hours_text
                except PlaywrightError:
                    pass

                # Extract location/address
                try:
                    location_selectors = [
                        '[data-testid="about_location"]',
                        '.x1i10hfl:has-text("Get directions")',
                        'span:has-text("·") + span',  # Often address follows a bullet point
                    ]

                    for selector in location_selectors:
                        elements = await self.page.query_selector_all(selector)
                        for element in elements:
                            text = await element.text_content()
                            if text and len(text.strip()) > 10:
                                # Check if it looks like an address
                                if any(
                                    indicator in text.lower()
                                    for indicator in [
                                        "street",
                                        "st",
                                        "ave",
                                        "avenue",
                                        "road",
                                        "rd",
                                        "drive",
                                        "dr",
                                        "lane",
                                        "ln",
                                        "blvd",
                                        "boulevard",
                                        ", ",
                                    ]
                                ):
                                    about_data["location"] = text.strip()
                                    break
                        if "location" in about_data:
                            break
                except PlaywrightError:
                    pass

                # If we found substantial information, return it
                if any(
                    key in about_data
                    for key in [
                        "about_description",
                        "external_websites",
                        "social_media_links",
                        "business_hours",
                        "location",
                    ]
                ):
                    # Clean up about_description if it looks like a URL with "Website" suffix
                    if "about_description" in about_data:
                        desc = about_data["about_description"]
                        # Remove "Website" suffix from URLs
                        if desc.startswith(("http://", "https://", "www.")) and desc.endswith(
                            "Website"
                        ):
                            about_data["about_description"] = desc[:-7].rstrip(
                                "/"
                            )  # Remove "Website" and trailing slash

                    return about_data

            except PlaywrightError as e:
                logger.debug("Failed to scrape about page %s: %s", about_url, str(e))
                continue

        return None

    def _extract_domain(self, url: str) -> str:
        """Return the network location (domain) portion of *url*.

        A fallback to the raw string is returned if the URL cannot be parsed.
        """
        try:
            parsed_url = urlparse(url)
            return parsed_url.netloc
        except (ValueError, AttributeError):
            return url


async def scrape_facebook_pages_concurrent(
    page_ids: Set[str],
    headless: bool = True,
    force_about: bool = False,
    max_concurrent: int = 3,
) -> Dict[str, Dict[str, Any]]:
    """Scrape multiple Facebook pages concurrently using multiple Playwright contexts."""

    overall_start = time.perf_counter()
    scraped_data = {}

    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)

    async def scrape_single_page(page_id: str, playwright_instance) -> tuple[str, Dict[str, Any]]:
        """Scrape one Facebook page in its own lightweight browser context.

        A new Chromium context is created to avoid cross-page contamination
        (cookies, cache). The semaphore limits the total number of concurrent
        contexts, protecting both the local machine and Facebook from
        excessive parallelism.
        """
        async with semaphore:  # Limit concurrent operations
            scraper = FacebookPageScraper()

            # Create new browser for this page (or reuse if available)
            browser = await playwright_instance.chromium.launch(
                headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )

            page = await context.new_page()
            await page.set_extra_http_headers(
                {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                }
            )

            # Set up the scraper with this context
            scraper.browser = browser
            scraper.context = context
            scraper.page = page

            try:
                page_data = await scraper.scrape_facebook_page(page_id, force_about=force_about)
                return page_id, page_data
            finally:
                await scraper.close()

    try:
        playwright = await async_playwright().start()

        # Create tasks for all pages
        tasks = [scrape_single_page(page_id, playwright) for page_id in sorted(page_ids)]

        print(
            f"  🚀 Starting {len(tasks)} concurrent scraping operations (max {max_concurrent} at once)..."
        )

        # Process tasks and show progress
        completed = 0
        for task in asyncio.as_completed(tasks):
            page_id, page_data = await task
            scraped_data[page_id] = page_data
            completed += 1

            # Show results as they complete
            if page_data.get("scrape_success"):
                name = page_data.get("name", "Unknown")
                category = page_data.get("category", "Unknown")
                duration = page_data.get("scrape_duration_seconds", 0)
                print(
                    f"    [{completed}/{len(tasks)}] {ansi.green}✅ {name}{ansi.reset} ({category}) - {ansi.cyan}{duration}s{ansi.reset}"
                )

                if page_data.get("username"):
                    print(f"    {ansi.blue}   @{page_data['username']}{ansi.reset}")

                if page_data.get("follower_count"):
                    followers = f"{page_data['follower_count']:,}"
                    print(f"    {ansi.yellow}   {followers} followers{ansi.reset}")

                # Show about page info if available
                if page_data.get("about_page_scraped"):
                    about_duration = page_data.get("about_scrape_duration_seconds", 0)
                    print(
                        f"    {ansi.cyan}   📋 About page data extracted ({about_duration}s){ansi.reset}"
                    )

                    if page_data.get("about_description"):
                        desc_preview = (
                            page_data["about_description"][:60] + "..."
                            if len(page_data["about_description"]) > 60
                            else page_data["about_description"]
                        )
                        print(f"    {ansi.cyan}   💬 {desc_preview}{ansi.reset}")

                    if page_data.get("external_websites"):
                        website_count = len(page_data["external_websites"])
                        print(f"    {ansi.cyan}   🌐 {website_count} website(s) found{ansi.reset}")

                    if page_data.get("social_media_links"):
                        social_media_count = len(page_data["social_media_links"])
                        print(
                            f"    {ansi.cyan}   👥 {social_media_count} social media links found{ansi.reset}"
                        )

                    if page_data.get("location"):
                        location_preview = (
                            page_data["location"][:40] + "..."
                            if len(page_data["location"]) > 40
                            else page_data["location"]
                        )
                        print(f"    {ansi.cyan}   📍 {location_preview}{ansi.reset}")
            else:
                error = page_data.get("error", "Unknown error")
                duration = page_data.get("scrape_duration_seconds", 0)
                print(
                    f"    [{completed}/{len(tasks)}] {ansi.red}❌ {page_id}{ansi.reset}: {error} - {ansi.cyan}{duration}s{ansi.reset}"
                )

    except (ValueError, RuntimeError) as e:
        logger.error("Error during playwright initialization: %s", e)
        sys.exit(1)
    finally:
        try:
            await playwright.stop()
        except PlaywrightError as e:
            logger.debug("Error stopping playwright: %s", e)

    overall_duration = time.perf_counter() - overall_start
    print(
        f"\n  {ansi.magenta}⚡ Total operation completed in {overall_duration:.2f} seconds{ansi.reset}"
    )
    logger.info("Concurrent scraping completed in %.2f seconds", overall_duration)

    return scraped_data


async def scrape_facebook_pages(
    page_ids: Set[str], headless: bool = True, force_about: bool = False
) -> Dict[str, Dict[str, Any]]:
    """Scrape multiple Facebook pages using Playwright (concurrent version for speed)."""
    return await scrape_facebook_pages_concurrent(page_ids, headless, force_about)


def save_page_mapping(
    page_data: Dict[str, Dict[str, Any]], output_dir: str = "data/facebook"
) -> str:
    """Save page mapping data to timestamped JSON file."""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"pages-{timestamp}.json"
    output_path = Path(output_dir) / filename

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Calculate success metrics
    successful = len([p for p in page_data.values() if p.get("scrape_success")])
    failed = len([p for p in page_data.values() if not p.get("scrape_success")])

    # Prepare output data
    output_data = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "total_pages": len(page_data),
            "successful_scrapes": successful,
            "failed_scrapes": failed,
            "extraction_method": "playwright_scraping",
            "note": "Data extracted by scraping Facebook pages with Playwright",
        },
        "pages": page_data,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return str(output_path)


async def main_async(argv: Optional[List[str]] = None):
    """Async main function to map Page IDs using Playwright."""
    parser = argparse.ArgumentParser(description="Map Facebook Page IDs using Playwright scraping")
    parser.add_argument(
        "--data-dir", default="data/facebook", help="Directory containing comment files"
    )
    parser.add_argument(
        "--output-dir", default="data/facebook", help="Directory to save page mapping"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with visible UI (default: headless)",
    )
    parser.add_argument(
        "--no-about",
        action="store_true",
        help="Skip about page scraping (default: scrape about pages)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=3,
        help="Number of concurrent browser contexts (default: 3)",
    )
    args = parser.parse_args(argv)

    # Set defaults (opposite of the no- flags)
    headless = not args.no_headless
    force_about = not args.no_about

    script_start = time.perf_counter()
    emoji = "🕷️" if not force_about else "🕷️📋"
    action = "scraping" if not force_about else "scraping with about pages"
    mode = "headless" if headless else "visible"
    print(
        f"{emoji} Mapping Page IDs using Playwright {action} ({mode} mode, {args.concurrent} concurrent)\n"
    )

    # Extract Page IDs from comment files
    print(f"{ansi.blue}Step 1:{ansi.reset} Extracting Page IDs from comment files...")
    step1_start = time.perf_counter()
    page_ids = extract_page_ids_from_comment_files(args.data_dir)
    step1_duration = time.perf_counter() - step1_start

    if not page_ids:
        print(f"{ansi.yellow}No Page IDs found to process.{ansi.reset}")
        return

    print(
        f"  {ansi.cyan}✅ Extracted {len(page_ids)} Page IDs in {step1_duration:.2f} seconds{ansi.reset}"
    )

    # Count posts per page for analytics
    print(f"\n{ansi.blue}Step 2:{ansi.reset} Analyzing post distribution per page...")
    step2_start = time.perf_counter()
    page_post_counts = count_posts_per_page(args.data_dir)
    step2_duration = time.perf_counter() - step2_start

    print("\nFound Page IDs with post counts:")
    for page_id in sorted(page_ids):
        post_count = page_post_counts.get(page_id, 0)
        print(f"  • {ansi.cyan}{page_id}{ansi.reset} ({ansi.yellow}{post_count} posts{ansi.reset})")

    print(f"  {ansi.cyan}✅ Analysis completed in {step2_duration:.2f} seconds{ansi.reset}")

    # Scrape Facebook pages
    print(f"\n{ansi.blue}Step 3:{ansi.reset} Scraping Facebook pages with Playwright...")
    step3_start = time.perf_counter()
    scraped_data = await scrape_facebook_pages_concurrent(
        page_ids,
        headless=headless,
        force_about=force_about,
        max_concurrent=args.concurrent,
    )
    step3_duration = time.perf_counter() - step3_start

    # Add post count analytics to scraped data
    for page_id, page_info in scraped_data.items():
        page_info["post_count_in_data"] = page_post_counts.get(page_id, 0)

    print(f"  {ansi.cyan}✅ Scraping completed in {step3_duration:.2f} seconds{ansi.reset}")

    # Save results
    print(f"\n{ansi.blue}Step 4:{ansi.reset} Saving page mapping...")
    step4_start = time.perf_counter()
    output_path = save_page_mapping(scraped_data, args.output_dir)
    step4_duration = time.perf_counter() - step4_start
    print(f"Page mapping saved to: {ansi.cyan}{output_path}{ansi.reset}")
    print(f"  {ansi.cyan}✅ Saved in {step4_duration:.2f} seconds{ansi.reset}")

    # Summary
    successful = len([p for p in scraped_data.values() if p.get("scrape_success")])
    failed = len([p for p in scraped_data.values() if not p.get("scrape_success")])

    total_script_duration = time.perf_counter() - script_start

    print(f"\n{ansi.green}✅ Playwright scraping completed!{ansi.reset}")
    print(f"  Total pages processed: {ansi.yellow}{len(scraped_data)}{ansi.reset}")
    print(f"  Successfully scraped: {ansi.green}{successful}{ansi.reset}")
    print(f"  Failed to scrape: {ansi.red}{failed}{ansi.reset}")
    print(f"  {ansi.magenta}🚀 Total script time: {total_script_duration:.2f} seconds{ansi.reset}")

    # Performance breakdown
    avg_page_time = step3_duration / len(page_ids) if page_ids else 0
    print(f"\n{ansi.blue}⏱️  Performance Breakdown:{ansi.reset}")
    print(f"  • Page extraction: {ansi.cyan}{step1_duration:.2f}s{ansi.reset}")
    print(f"  • Post counting: {ansi.cyan}{step2_duration:.2f}s{ansi.reset}")
    print(
        f"  • Concurrent scraping: {ansi.cyan}{step3_duration:.2f}s{ansi.reset} ({ansi.yellow}{avg_page_time:.2f}s avg/page{ansi.reset})"
    )
    print(f"  • Data saving: {ansi.cyan}{step4_duration:.2f}s{ansi.reset}")

    if successful > 0:
        print(f"\n{ansi.magenta}📋 Successfully identified pages:{ansi.reset}")
        for page_id, page_info in scraped_data.items():
            if page_info.get("scrape_success"):
                name = page_info.get("name", "Unknown")
                category = page_info.get("category", "Unknown")
                post_count = page_info["post_count_in_data"]
                username = page_info.get("username", "")
                username_display = f" (@{username})" if username else ""
                duration = page_info.get("scrape_duration_seconds", 0)
                print(
                    f"  • {ansi.yellow}{name}{ansi.reset}{username_display} - {category} ({post_count} posts, {duration}s)"
                )

    # Highlight the page with most posts
    if page_post_counts:
        max_page = max(page_post_counts.items(), key=lambda x: x[1])
        max_page_id, max_count = max_page
        max_page_name = scraped_data.get(max_page_id, {}).get("name", "Unknown")
        print(
            f"\n{ansi.magenta}🎯 Most active page:{ansi.reset} {ansi.yellow}{max_page_name}{ansi.reset} ({ansi.cyan}{max_page_id}{ansi.reset}) - {ansi.yellow}{max_count} posts{ansi.reset}"
        )

    logger.info(
        "Script completed in %.2f seconds with %d successful scrapes",
        total_script_duration,
        successful,
    )


def main(argv: Optional[List[str]] = None):
    """Main function wrapper for async execution."""
    if sys.platform == "win32":
        # Better event loop handling for Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main_async(argv))
        # Script completed successfully - any warnings below are just Windows cleanup noise
        if sys.platform == "win32":
            print(f"\n{ansi.green}✨ Script completed successfully!{ansi.reset}")
            print(
                f"{ansi.yellow}Note:{ansi.reset} Any asyncio warnings above are just Windows cleanup noise and can be ignored."
            )
    except KeyboardInterrupt:
        print(f"\n{ansi.yellow}Script interrupted by user{ansi.reset}")
    except Exception as e:
        print(f"\n{ansi.red}Error: {e}{ansi.reset}")
        sys.exit(1)


if __name__ == "__main__":
    main()
