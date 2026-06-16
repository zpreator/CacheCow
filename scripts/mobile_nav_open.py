"""Screenshot the home page with the hamburger menu open."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8501"
OUT = Path(__file__).parent / "mobile_screenshots"

IPHONE = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 3,
    "is_mobile": True,
    "has_touch": True,
}

async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(**IPHONE)
        page = await ctx.new_page()

        await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        await page.fill('input[name="username"]', "darthpreator")
        await page.fill('input[name="password"]', "admin")
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await page.click('button[type="submit"]')

        await page.goto(f"{BASE}/", wait_until="networkidle")
        await page.wait_for_timeout(500)

        # Click hamburger to open menu
        await page.click('#hamburger-btn')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / "nav_open.png"), full_page=False)
        print("Saved nav_open.png")

        await browser.close()

asyncio.run(run())
