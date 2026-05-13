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
            # Try common selectors for age gate buttons
            selectors = [
                "button:has-text('I am 18')",
                "button:has-text('18+')",
                "button:has-text('Enter')",
                "button:has-text('Yes')",
                "button:has-text('I Agree')",
                "button:has-text('Confirm')",
                ".age-gate button",
                "#age-gate button",
                "[class*='age'] button",
            ]

            for selector in selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if btn:
                        await btn.click()
                        logger.info(f"Clicked age gate button: {selector}")
                        await asyncio.sleep(2)
                        return
                except Exception:
                    continue

            logger.info("No age gate found or already dismissed.")

        except Exception as e:
            logger.warning(f"Age gate handling error: {e}")

    async def _enable_nsfw(self):
        """Enable NSFW/18+ toggle on the page."""
        try:
            nsfw_selectors = [
                "input[type='checkbox'][id*='nsfw']",
                "input[type='checkbox'][id*='adult']",
                "input[type='checkbox'][id*='18']",
                "label:has-text('NSFW')",
                "label:has-text('18+')",
                "label:has-text('Adult')",
                "[class*='nsfw'] input",
                "[class*='adult'] input",
            ]

            for selector in nsfw_selectors:
                try:
                    el = await self.page.wait_for_selector(selector, timeout=3000)
                    if el:
                        # Check if it's already enabled
                        is_checked = await el.is_checked() if "input" in selector else False
                        if not is_checked:
                            await el.click()
                            logger.info(f"Enabled NSFW toggle: {selector}")
                        else:
                            logger.info("NSFW already enabled.")
                        await asyncio.sleep(1)
                        return
                except Exception:
                    continue

            logger.info("No NSFW toggle found — may not be needed or already on.")

        except Exception as e:
            logger.warning(f"NSFW toggle error: {e}")

    async def generate(self, prompt: str) -> str | None:
        """
        Type the prompt, click generate, wait for image, save and return path.
        Returns the image file path, or None on failure.
        """
        if not self.ready:
            logger.error("Browser not ready!")
            return None

        try:
            logger.info(f"Generating image for prompt: {prompt}")

            # Find the prompt input field
            input_selectors = [
                "textarea[placeholder*='describe']",
                "textarea[placeholder*='character']",
                "textarea[placeholder*='prompt']",
                "input[placeholder*='describe']",
                "input[placeholder*='character']",
                "input[placeholder*='prompt']",
                "textarea",
                "#prompt",
                ".prompt-input",
                "[class*='prompt'] textarea",
                "[class*='input'] textarea",
            ]

            input_el = None
            for selector in input_selectors:
                try:
                    input_el = await self.page.wait_for_selector(selector, timeout=3000)
                    if input_el:
                        logger.info(f"Found input: {selector}")
                        break
                except Exception:
                    continue

            if not input_el:
                logger.error("Could not find prompt input field!")
                return None

            # Clear and type prompt
            await input_el.click(click_count=3)
            await input_el.fill(prompt)
            await asyncio.sleep(0.5)

            # Find and click the generate button
            generate_selectors = [
                "button:has-text('Generate')",
                "button:has-text('Create')",
                "button:has-text('Make')",
                "button[type='submit']",
                ".generate-btn",
                "#generate-btn",
                "[class*='generate'] button",
                "[class*='create'] button",
            ]

            gen_btn = None
            for selector in generate_selectors:
                try:
                    gen_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if gen_btn:
                        logger.info(f"Found generate button: {selector}")
                        break
                except Exception:
                    continue

            if not gen_btn:
                logger.error("Could not find generate button!")
                return None

            await gen_btn.click()
            logger.info("Clicked generate, waiting for image...")

            # Wait for the image to appear/change
            image_path = await self._wait_for_image()
            return image_path

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return None

    async def _wait_for_image(self, timeout: int = 60) -> str | None:
        """Wait for image to be generated and save it."""
        try:
            image_selectors = [
                "img.result",
                "img.output",
                ".result img",
                ".output img",
                "[class*='result'] img",
                "[class*='output'] img",
                "[class*='generated'] img",
                "canvas",
            ]

            start = time.time()
            while time.time() - start < timeout:
                for selector in image_selectors:
                    try:
                        el = await self.page.query_selector(selector)
                        if el:
                            # Check image has loaded
                            if selector == "canvas":
                                # Screenshot the canvas
                                filename = f"{SCREENSHOTS_DIR}/gen_{int(time.time())}.png"
                                await el.screenshot(path=filename)
                                logger.info(f"Captured canvas to {filename}")
                                return filename
                            else:
                                src = await el.get_attribute("src")
                                natural_width = await el.evaluate("el => el.naturalWidth")
                                if src and natural_width and natural_width > 50:
                                    filename = f"{SCREENSHOTS_DIR}/gen_{int(time.time())}.png"
                                    await el.screenshot(path=filename)
                                    logger.info(f"Captured image to {filename}")
                                    return filename
                    except Exception:
                        continue

                await asyncio.sleep(2)

            # Fallback: full page screenshot
            logger.warning("Could not find image element, taking full page screenshot...")
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
