#!/usr/bin/env python3
"""Render the X still and report ink coverage against the 4-5% target."""
import asyncio, os
from pathlib import Path
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "pipeline-x-2x.png"
SIZE = 1080


async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="chrome")
        except Exception:
            browser = await p.chromium.launch(
                executable_path=os.path.expanduser("~/.local/bin/chromium"))
        page = await browser.new_page(viewport={"width": SIZE, "height": SIZE},
                                      device_scale_factor=2)
        await page.goto((HERE / "index.html").as_uri(), wait_until="load")
        # prove the webfonts actually loaded, not just requested
        loaded = await page.evaluate("""(() => ({
            sg: document.fonts.check("700 104px 'Space Grotesk'"),
            mono: document.fonts.check("400 17px 'IBM Plex Mono'"),
            inter: document.fonts.check("400 20px 'Inter'")
        }))()""")
        print("fonts loaded:", loaded)
        await page.screenshot(path=str(OUT), clip={"x": 0, "y": 0, "width": SIZE, "height": SIZE})
        await browser.close()

    print("saved:", OUT)


if __name__ == "__main__":
    asyncio.run(main())
