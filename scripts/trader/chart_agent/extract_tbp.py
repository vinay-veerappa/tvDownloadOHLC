"""Extract TBP PDF content using Gemini SDK — one page at a time to avoid rate limits."""
import asyncio
import os
import sys
from pathlib import Path

# Load .env
_REPO = Path(__file__).parent.parent.parent.parent
_env_file = _REPO / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v

import google.antigravity as agy

PAGES_DIR = _REPO / "data" / "vision" / "charts" / "tbp_pages"
OUTPUT = _REPO / "data" / "vision" / "tbp_extracted.md"

PROMPT = """Read this page from the 'Trader Blue Print Series' PDF (a TCM/ICT trading education document).
Extract ALL text, rules, definitions, time windows, concepts, and diagrams you can read.
Focus especially on:
- The 7 Rules (Rule 1 through Rule 7)
- Submission range (time window, OHLC, 50%)
- ONS Profiles
- Dealing range definition
- Any time windows, killzones, macros
- Order Pairing Hierarchy
- TCM Timeframes

Output the extracted content as clean markdown. Be thorough — read everything on the page."""


async def read_page(page_path: Path, page_num: int) -> str:
    """Read a single page with Gemini."""
    config = agy.LocalAgentConfig(
        system_instructions="You are an expert at reading trading education slides and extracting structured information. Output clean markdown."
    )
    img = agy.Image.from_file(str(page_path))

    async with agy.Agent(config) as agent:
        response = await agent.chat([img, f"Page {page_num}. {PROMPT}"])
        chunks = []
        async for token in response:
            chunks.append(token)
        return "".join(chunks)


async def main():
    pages = sorted(PAGES_DIR.glob("page_*.png"))
    print(f"Found {len(pages)} pages to read")

    all_content = []
    for i, page_path in enumerate(pages):
        page_num = int(page_path.stem.split("_")[1])
        print(f"  Reading page {page_num} ({i+1}/{len(pages)})...", end=" ", flush=True)
        try:
            content = await read_page(page_path, page_num)
            all_content.append(f"\n\n--- PAGE {page_num} ---\n\n{content}")
            print(f"{len(content)} chars")
        except Exception as e:
            err = str(e)[:100]
            print(f"ERROR: {err}")
            all_content.append(f"\n\n--- PAGE {page_num} ---\n\n[EXTRACTION ERROR: {err}]")

        # Rate limit: wait between pages to avoid 429
        if i < len(pages) - 1:
            await asyncio.sleep(5)

    full = "# Trader Blue Print Series — Extracted Content\n\n" + "".join(all_content)
    OUTPUT.write_text(full, encoding="utf-8")
    print(f"\nSaved {len(full)} chars to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())