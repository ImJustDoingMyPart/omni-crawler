# 🕷️ Omni-Crawler: Web-to-LLM Engine

This project is a scraping tool designed to convert entire documentation sites into a single clean Markdown file. It is optimized to feed language models (LLMs) with accurate context, eliminating unnecessary noise from websites.

## ✨ Key Features

- **Dual Interface:** Works as a command-line tool (CLI) or as a local web application (GUI) with Streamlit.
- **Anti-Bot Detection:** Implements `User-Agent` rotation and real headers to avoid blocks (successfully tested against protected servers such as Caddy).
- **Smart Cleaning:** Uses text density filters to remove menus, footers, and sidebars, retaining only useful content.
- **Asynchronous and Parallel:** Based on `Crawl4AI` and `Playwright`, it allows you to download dozens of pages in seconds.

---

## 🚀 Quick Installation

### 1. Clone and prepare environment

```bash
git clone [https://github.com/ImJustDoingMyPart/omni-crawler.git](https://github.com/ImJustDoingMyPart/omni-crawler.git)
cd omni-crawler
```

*You can use your preferred package manager:*

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

## 🚀 How to Use
### Option A: Terminal Mode (CLI)
Ideal for automated processes or quick use if you already know the URL.

```bash
uv run python crawler.py [https://docs.ejemplo.com/](https://docs.ejemplo.com/) -o my_documentation.md
```

### Option B: Graphical Mode (GUI)
User-friendly interface with progress bar and download button. Just run the script without arguments:

```bash
uv run python crawler.py
```

*The script will detect the absence of parameters and automatically launch Streamlit in your browser.*

## 📝 The `crawler.py` Script
The main file (crawler.py) integrates the stealth logic and content cleaning. Make sure your file has the hybrid structure that allows both execution modes.

### Tips for Use
* Close the program: Use Ctrl + C in the terminal to stop crawling or shut down the GUI server.

* Context for AI: The generated file (.md) can be uploaded directly to ChatGPT, Claude, Gemini, or your local Open WebUI instance to give them “superpowers” over a specific tool.

## ❓ Troubleshooting
Python version error: If your system uses 3.14 (experimental), make sure you have run uv python pin 3.12 and that the pyproject.toml file reflects requires-python = “>=3.12”.

File download failure: The script is designed to ignore .zip or binary files that cannot be converted to text.

## 🤝 Contributions
This tool was heavily vibe-coded by a non-dev. You are welcome to make your suggestions and contributions as you prefer.