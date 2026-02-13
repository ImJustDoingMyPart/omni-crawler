import os
import sys
import asyncio
import argparse
import subprocess
from datetime import datetime

# Importamos Streamlit de forma segura
try:
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except ImportError:
    st = None

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# --- LÓGICA CENTRAL DE CRAWLING ---
async def ejecutar_crawling(url, output_file, log_callback=print):
    domain = url.split("//")[-1].split("/")[0]
    log_callback(f"🚀 Iniciando misión en: {url}")

    # 1. Configuración del Filtro
    filtro_limpieza = PruningContentFilter(
        threshold=0.48,      
        threshold_type="dynamic",
        min_word_threshold=5
    )
    generador_md = DefaultMarkdownGenerator(content_filter=filtro_limpieza)

    # 2. Configuración del Navegador (MODO SIGILO ACTUALIZADO)
    browser_cfg = BrowserConfig(
        headless=True,
        verbose=False,
        user_agent_mode="random",
        headers={
            # TRUCO 1: Decimos que venimos de Google para ganar confianza
            "Referer": "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
    )
    
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=generador_md,
        stream=False,
        page_timeout=60000,
        # TRUCO 2: Esperamos 2 segundos antes de capturar (Simula lectura humana y relaja al servidor)
        delay_before_return_html=2.0 
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        # PASO A: Indexar
        log_callback("🔍 Escaneando índice...")
        result_index = await crawler.arun(url=url, config=run_cfg)
        
        if not result_index.success:
            log_callback(f"❌ Error crítico: {result_index.error_message}")
            return False

        # PASO B: Filtrar enlaces
        urls_encontradas = {url}
        for link in result_index.links.get("internal", []):
            href = link.get("href", "")
            if href.startswith(url) and "#" not in href:
                urls_encontradas.add(href)

        lista_urls = list(urls_encontradas)
        log_callback(f"✅ Encontradas {len(lista_urls)} páginas. Descargando con pausas de seguridad...")

        # PASO C: Descarga Masiva
        results = await crawler.arun_many(lista_urls, config=run_cfg)

        # PASO D: Guardado
        log_callback("💾 Consolidando archivo...")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Documentación de {domain}\n")
            f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            
            for res in results:
                if res.success:
                    f.write(f"\n\n---\n## FUENTE: {res.url}\n---\n\n")
                    f.write(res.markdown.fit_markdown)
                else:
                    log_callback(f"⚠️ Falló página: {res.url}")

        log_callback(f"🎉 ¡Éxito! Archivo guardado: {output_file}")
        return True

# --- LÓGICA DE INTERFAZ GRÁFICA (GUI) ---
def run_gui():
    st.set_page_config(page_title="Omni-Crawler", page_icon="🕷️")
    st.title("🕷️ Omni-Crawler")
    st.markdown("Extractor de documentación para IA (Powered by Crawl4AI)")

    with st.form("crawler_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            url_input = st.text_input("URL de Documentación", placeholder="https://caddyserver.com/docs/")
        with col2:
            filename = st.text_input("Nombre Archivo", value="docs.md")
        
        submitted = st.form_submit_button("🚀 Iniciar Extracción")

    log_container = st.empty()
    
    def gui_logger(msg):
        if "❌" in msg: log_container.error(msg)
        elif "✅" in msg: log_container.success(msg)
        elif "🎉" in msg: log_container.balloons(); st.success(msg)
        else: log_container.info(msg)

    if submitted and url_input:
        asyncio.run(ejecutar_crawling(url_input, filename, gui_logger))
        
        if os.path.exists(filename):
            with open(filename, "r") as f:
                st.download_button("📥 Bajar Markdown", f, file_name=filename)

# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    is_running_as_streamlit = False
    try:
        if get_script_run_ctx():
            is_running_as_streamlit = True
    except:
        pass

    if is_running_as_streamlit:
        run_gui()
    else:
        parser = argparse.ArgumentParser(description="Crawler Híbrido CLI/GUI")
        parser.add_argument("url", nargs="?", help="URL a procesar")
        parser.add_argument("-o", "--output", default="output.md", help="Archivo de salida")
        parser.add_argument("--gui", action="store_true", help="Forzar modo gráfico")
        
        args = parser.parse_args()

        if args.gui or not args.url:
            print("🖥️  Lanzando interfaz gráfica...")
            sys.argv = ["streamlit", "run", __file__]
            sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", __file__]))
        else:
            print("📟 Modo Terminal activado")
            asyncio.run(ejecutar_crawling(args.url, args.output))