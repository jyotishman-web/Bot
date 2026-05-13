import asyncio
import logging
import os
import time
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)

PERCHANCE_URL = "https://perchance.org/ai-character-generator"
SCREENSHOTS_DIR = "temp_images"


class PerchanceBrowser:
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.ready = False

    async def init(self):
        """Launch browser and open perchance, handle 18+ gate."""
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        self.page = await self.context.new_page()

        logger.info(f"Navigating to {PERCHANCE_URL}...")
        await self.page.goto(PERCHANCE_URL, wait_until="networkidle", timeout=60000)

        # Wait a moment for JS to load
        await asyncio.sleep(3)

        # Handle 18+ age gate
        await self._handle_age_gate()

        # Enable NSFW/18+ toggle
        await self._enable_nsfw()

        self.ready = True
        logger.info("Browser initialized and ready.")

    async def _handle_age_gate(self):
        """Click through any 18+ confirmation dialog."""
        try:
            await asyncio.sleep(2)
            # Perchance uses an iframe-based generator, check for age gate in main page
            selectors = [
                "button:has-text('I am 18')",
                "button:has-text('18+')",
                "button:has-text('Enter')",
                "button:has-text('Yes')",
                "button:has-text('I Agree')",
                "button:has-text('Confirm')",
                "button:has-text('Continue')",
            ]
            for selector in selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=2000)
                    if btn:
                        await btn.click()
                        logger.info(f"Clicked age gate: {selector}")
                        await asyncio.sleep(2)
                        return
                except Exception:
                    continue
            logger.info("No age gate found.")
        except Exception as e:
            logger.warning(f"Age gate error: {e}")

    async def _enable_nsfw(self):
        """Enable NSFW toggle — perchance embeds the generator in an iframe."""
        try:
            await asyncio.sleep(3)

            # Try finding NSFW toggle in main page first
            nsfw_selectors = [
                "input[id*='nsfw']",
                "input[id*='adult']",
                "label:has-text('NSFW')",
                "label:has-text('18+')",
                "label:has-text('Adult')",
                "input[type='checkbox']",
            ]
            for selector in nsfw_selectors:
                try:
                    el = await self.page.wait_for_selector(selector, timeout=2000)
                    if el:
                        try:
                            checked = await el.is_checked()
                            if not checked:
                                await el.click()
                                logger.info(f"Enabled NSFW: {selector}")
                            else:
                                logger.info("NSFW already on")
                        except Exception:
                            await el.click()
                        await asyncio.sleep(1)
                        return
                except Exception:
                    continue

            # Try inside iframes
            for frame in self.page.frames:
                for selector in nsfw_selectors:
                    try:
                        el = await frame.wait_for_selector(selector, timeout=1000)
                        if el:
                            await el.click()
                            logger.info(f"Enabled NSFW in iframe: {selector}")
                            await asyncio.sleep(1)
                            return
                    except Exception:
                        continue

            logger.info("No NSFW toggle found.")
        except Exception as e:
            logger.warning(f"NSFW toggle error: {e}")

    async def _get_frame(self):
        """Return the frame containing the generator (iframe or main page)."""
        # Wait for iframe to load
        await asyncio.sleep(2)
        for frame in self.page.frames:
            try:
                # Look for generate button or textarea in any frame
                el = await frame.query_selector("textarea, button")
                if el:
                    logger.info(f"Found generator in frame: {frame.url}")
                    return frame
            except Exception:
                continue
        return self.page  # fallback to main page

    async def generate(self, prompt: str) -> str | None:
        """Type prompt, click generate, wait for image."""
        if not self.ready:
            return None
        try:
            logger.info(f"Generating: {prompt}")

            # Take a debug screenshot to see what page looks like
            debug_path = f"{SCREENSHOTS_DIR}/debug_{int(time.time())}.png"
            await self.page.screenshot(path=debug_path)
            logger.info(f"Debug screenshot saved: {debug_path}")

            frame = await self._get_frame()

            # --- Find textarea / input ---
            input_el = None
            input_selectors = [
                "textarea",
                "input[type='text']",
                "[contenteditable='true']",
                "#prompt",
                ".prompt",
            ]
            for sel in input_selectors:
                try:
                    el = await frame.wait_for_selector(sel, timeout=3000)
                    if el and await el.is_visible():
                        input_el = el
                        logger.info(f"Found input: {sel}")
                        break
                except Exception:
                    continue

            if not input_el:
                logger.error("No input found!")
                return None

            await input_el.click()
            await input_el.triple_click()
            await input_el.fill(prompt)
            await asyncio.sleep(0.5)

            # --- Find generate button ---
            btn_el = None
            btn_selectors = [
                "button:has-text('Generate')",
                "button:has-text('Create')",
                "button:has-text('Make')",
                "button[type='submit']",
                "button",
            ]
            for sel in btn_selectors:
                try:
                    el = await frame.wait_for_selector(sel, timeout=3000)
                    if el and await el.is_visible():
                        btn_el = el
                        logger.info(f"Found button: {sel}")
                        break
                except Exception:
                    continue

            if not btn_el:
                logger.error("No generate button found!")
                return None

            await btn_el.click()
            logger.info("Clicked generate, waiting for image...")

            return await self._wait_for_image(frame)

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return None

    async def _wait_for_image(self, frame, timeout: int = 90) -> str | None:
        """Wait for image to appear and save it."""
        try:
            start = time.time()
            last_src = None

            while time.time() - start < timeout:
                # Try all frames including main page
                frames_to_check = list(self.page.frames) + [self.page]

                for f in frames_to_check:
                    try:
                        # Check for img tags
                        imgs = await f.query_selector_all("img")
                        for img in imgs:
                            try:
                                src = await img.get_attribute("src")
                                w = await img.evaluate("el => el.naturalWidth")
                                h = await img.evaluate("el => el.naturalHeight")
                                if src and w and w > 100 and h > 100 and src != last_src:
                                    if src.startswith("data:") or src.startswith("http") or src.startswith("blob"):
                                        last_src = src
                                        filename = f"{SCREENSHOTS_DIR}/gen_{int(time.time())}.png"
                                        await img.screenshot(path=filename)
                                        logger.info(f"Captured image {w}x{h}: {filename}")
                                        return filename
                            except Exception:
                                continue

                        # Check for canvas
                        canvases = await f.query_selector_all("canvas")
                        for canvas in canvases:
                            try:
                                w = await canvas.evaluate("el => el.width")
                                h = await canvas.evaluate("el => el.height")
                                if w and w > 100 and h > 100:
                                    filename = f"{SCREENSHOTS_DIR}/gen_{int(time.time())}.png"
                                    await canvas.screenshot(path=filename)
                                    logger.info(f"Captured canvas {w}x{h}: {filename}")
                                    return filename
                            except Exception:
                                continue
                    except Exception:
                        continue

                await asyncio.sleep(2)

            # Final fallback: full page screenshot
            logger.warning("Timeout — taking full page screenshot")
            filename = f"{SCREENSHOTS_DIR}/gen_{int(time.time())}_fallback.png"
            await self.page.screenshot(path=filename, full_page=False)
            return filename

        except Exception as e:
            logger.error(f"Wait for image error: {e}")
            return None

    async def close(self):
        """Shut down browser."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed.")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
