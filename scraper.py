import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

OUTPUT_JSON_NAME = "output.json"


async def extract_top_articles(
    page,
    limit: int = 5,
    category_name: str = "मनोरञ्जन",
) -> List[Dict[str, Any]]:
    """
    Extracts top `limit` valid articles from the Entertainment listing page.

    Rules followed:
    - Each article is inside `div.category`
    - Take first N valid articles (skip blocks missing title)
    - title from `h2 a`
    - image_url from `img[src]` or `img[data-src]`
    - author from `div.author-name` (or null if missing)
    """
    category_divs = page.locator("div.category")
    items: List[Dict[str, Any]] = []

    total = await category_divs.count()
    for i in range(total):
        if len(items) >= limit:
            break

        div = category_divs.nth(i)

        title_el = div.locator("h2 a").first
        title = (await title_el.text_content() or "").strip()
        if not title:
            continue

        img = div.locator("img").first
        src = (await img.get_attribute("src")) or ""
        data_src = (await img.get_attribute("data-src")) or ""
        image_url = (src or data_src).strip()

        author: Optional[str] = None
        if await div.locator("div.author-name").count():
            # Prefer the linked author name if present.
            a_author = div.locator("div.author-name a").first
            author_text = (await a_author.text_content() or "").strip()
            if not author_text:
                author_text = (await div.locator("div.author-name").first.text_content() or "").strip()
            if author_text:
                author = author_text

        items.append(
            {
                "title": title,
                "image_url": image_url,
                "category": category_name,
                "author": author,
            }
        )

    return items


async def extract_entertainment(page) -> List[Dict[str, Any]]:
    """Navigate to entertainment page and extract top articles."""
    url = "https://ekantipur.com/entertainment"
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_selector("div.category h2 a", timeout=60000)
    return await extract_top_articles(page, limit=5, category_name="मनोरञ्जन")


async def extract_cartoon(page) -> Dict[str, Any]:
    """Navigate to cartoon page and extract cartoon of the day."""
    cartoon_url = "https://ekantipur.com/cartoon"
    await page.goto(cartoon_url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_selector("div.cartoon-wrapper", timeout=60000)

    cartoon_wrapper = page.locator("div.cartoon-wrapper").first
    cartoon_p = cartoon_wrapper.locator("div.cartoon-description p").first
    cartoon_text = (await cartoon_p.text_content() or "").strip()

    author = None
    title = cartoon_text
    # Normalize dash variants: "-"/"–"/"—"
    normalized_text = cartoon_text.replace("–", "-").replace("—", "-")
    if "-" in normalized_text:
        left, _, right = normalized_text.partition("-")
        title = left.strip()
        author_candidate = right.strip()
        if author_candidate:
            author = author_candidate

    img = cartoon_wrapper.locator("img").first
    src = (await img.get_attribute("src")) or ""
    data_src = (await img.get_attribute("data-src")) or ""
    image_url = (src or data_src).strip()

    return {
        "title": title,
        "image_url": image_url,
        "author": author,
    }


async def run() -> Dict[str, Any]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # Create two pages for concurrent navigation
        page_ent = await context.new_page()
        page_cartoon = await context.new_page()

        # Run both extraction tasks concurrently
        ent_task = asyncio.create_task(extract_entertainment(page_ent))
        cart_task = asyncio.create_task(extract_cartoon(page_cartoon))

        entertainment_items, cartoon_data = await asyncio.gather(ent_task, cart_task)

        await browser.close()

        return {
            "entertainment_news": entertainment_items,
            "cartoon_of_the_day": cartoon_data,
        }


def main() -> None:
    result = asyncio.run(run())

    output_path = Path(__file__).resolve().parent / OUTPUT_JSON_NAME
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print JSON to stdout (same as original)
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()