# 🕷️ Omni-Crawler: Web-to-LLM Engine

This project is a scraping tool designed to convert entire documentation sites into a single clean Markdown file. It is optimized to feed language models (LLMs) with accurate context, eliminating unnecessary noise from websites.

## ✨ Key Features

- **3 Crawling Modes:** Static pages, "Load More" buttons, and infinite scroll — the right strategy for each site.
- **Anti-Bot Detection:** `User-Agent` rotation, `simulate_user`, `override_navigator`, and `magic` mode to avoid blocks.
- **Smart Cleaning:** Text density filters to remove menus, footers, and sidebars, retaining only useful content.
- **Shadow DOM & Iframes:** Automatically flattens Shadow DOM and inlines iframe content.
- **Cookie/GDPR Popups:** Auto-removes consent popups from known CMP providers (OneTrust, Cookiebot, etc.).
- **Robust URL Filtering:** Normalizes URLs and excludes binary files (PDFs, images, fonts, etc.).
- **Automatic Retries:** Failed pages are retried once automatically.
- **Controlled Concurrency:** Limits simultaneous downloads to avoid overwhelming servers.
- **Dual Interface:** Works as a CLI tool or as a local web app (GUI) with Streamlit.

---

## 🚀 Quick Installation

### 1. Clone and prepare environment

```bash
git clone https://github.com/ImJustDoingMyPart/omni-crawler.git
cd omni-crawler
```

**With `uv` (Recommended):**
```bash
uv sync
uv run playwright install
```

**With `pip`:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install crawl4ai streamlit
python -m playwright install
```

### 2. System dependencies (Linux)

If you experience errors with your browser, install the necessary dependencies:

* Debian/Ubuntu: `sudo playwright install-deps`
* Arch/CachyOS: `paru -S enchant libmanette flite harfbuzz-icu hyphen`

---

## 🚀 How to Use

### Option A: Terminal Mode (CLI)

**Static mode** (default) — for normal documentation sites:
```bash
uv run python crawler.py https://docs.ejemplo.com/ -o my_docs.md
```

**Load More mode** — for sites with a "Load More" / "Show More" button:
```bash
uv run python crawler.py https://blog.ejemplo.com/ --mode loadmore \
  --load-more-selector "button.load-more" \
  --load-more-clicks 15
```

**Scroll mode** — for sites with infinite scroll:
```bash
uv run python crawler.py https://feed.ejemplo.com/ --mode scroll \
  --scroll-count 30
```

**Control concurrency** — to be gentler on the target server:
```bash
uv run python crawler.py https://docs.ejemplo.com/ --max-concurrent 3
```

### Option B: Graphical Mode (GUI)

User-friendly interface with mode selector and download button. Just run without arguments:

```bash
uv run python crawler.py
```

### All CLI Options

```
usage: crawler.py [-h] [-o OUTPUT] [--gui]
                  [--mode {static,loadmore,scroll}]
                  [--load-more-selector SELECTOR]
                  [--load-more-clicks N]
                  [--scroll-count N]
                  [--max-concurrent N]
                  [url]

Arguments:
  url                       URL to process
  -o, --output              Output file (default: output.md)
  --gui                     Force graphical mode
  --mode                    Crawling mode: static, loadmore, scroll
  --load-more-selector      CSS selector for the "Load More" button
  --load-more-clicks        Max clicks on "Load More" (default: 10)
  --scroll-count            Number of scrolls in scroll mode (default: 20)
  --max-concurrent          Max concurrent page downloads (default: 5)
```

---

## 💡 Tips

* **Close the program:** Use `Ctrl + C` in the terminal to stop crawling or shut down the GUI server.
* **Context for AI:** The generated `.md` file can be uploaded directly to ChatGPT, Claude, Gemini, or your local Open WebUI instance to give them "superpowers" over a specific tool.
* **Finding the right selector:** Open the target site in your browser, right-click the "Load More" button → Inspect, and copy the CSS selector.

## ❓ Troubleshooting

* **Python version error:** If your system uses 3.14, make sure you have run `uv python pin 3.12` and that `pyproject.toml` reflects `requires-python = ">=3.12"`.
* **File download failure:** The script automatically ignores binary files (images, PDFs, fonts, etc.).
* **Blocked by server:** Try reducing concurrency with `--max-concurrent 2` and using `static` mode first.

## 🤝 Contributions

This tool was heavily vibe-coded by a non-dev. You are welcome to make your suggestions and contributions as you prefer.