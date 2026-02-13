import os
import sys
import asyncio
import argparse
import subprocess
from datetime import datetime

# Importamos Streamlit pero manejamos el caso de que no se esté ejecutando como tal
try:
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except ImportError:
    st = None

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# --- LÓGICA CENTRAL DE CRAWLING (El "Motor") ---
async def ejecutar_crawling(url, output_file, log_callback=print):
    """
    Esta función es agnóstica: no sabe si corre en terminal o GUI.
    Solo recibe una URL y una función para reportar progreso (log_callback).
    """
    domain = url.split("//")[-1].split("/")[0]
    log_callback(f"🚀 Iniciando misión en: {url}")

    # 1. Configuración del Filtro (Limpieza)
    filtro_limpieza = PruningContentFilter(
        threshold=0.48,      
        threshold_type="dynamic",
        min_word_threshold=5
    )
    generador_md = DefaultMarkdownGenerator(content_filter=filtro_limpieza)

    # 2. Configuración del Navegador (Modo Sigilo Anti-Bloqueo)
    browser_cfg = BrowserConfig(
        headless=True,
        verbose=False, # Menos ruido en terminal
        user_agent_mode="random",
        headers={
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
    )
    
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=generador_md,
        stream=False,
        page_timeout=60000 
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
            # Lógica: debe empezar con la URL base y no ser un ancla (#)
            if href.startswith(url) and "#" not in href:
                urls_encontradas.add(href)

        lista_urls = list(urls_encontradas)
        log_callback(f"✅ Encontradas {len(lista_urls)} páginas. Iniciando descarga masiva...")

        # PASO C: Descarga
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

    # Formulario
    with st.form("crawler_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            url_input = st.text_input("URL de Documentación", placeholder="https://caddyserver.com/docs/")
        with col2:
            filename = st.text_input("Nombre Archivo", value="docs.md")
        
        submitted = st.form_submit_button("🚀 Iniciar Extracción")

    # Área de logs visual
    log_container = st.empty()
    
    def gui_logger(msg):
        # Función auxiliar para imprimir en la web
        if "❌" in msg: log_container.error(msg)
        elif "✅" in msg: log_container.success(msg)
        elif "🎉" in msg: log_container.balloons(); st.success(msg)
        else: log_container.info(msg)

    if submitted and url_input:
        asyncio.run(ejecutar_crawling(url_input, filename, gui_logger))
        
        # Botón de descarga post-proceso
        if os.path.exists(filename):
            with open(filename, "r") as f:
                st.download_button("📥 Bajar Markdown", f, file_name=filename)

# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    # Detectar si estamos corriendo BAJO Streamlit
    # (Streamlit modifica el entorno de ejecución)
    is_running_as_streamlit = False
    try:
        if get_script_run_ctx():
            is_running_as_streamlit = True
    except:
        pass

    if is_running_as_streamlit:
        # CASO 1: Ya estamos en modo GUI
        run_gui()
    else:
        # Analizamos argumentos de terminal
        parser = argparse.ArgumentParser(description="Crawler Híbrido CLI/GUI")
        parser.add_argument("url", nargs="?", help="URL a procesar")
        parser.add_argument("-o", "--output", default="output.md", help="Archivo de salida")
        parser.add_argument("--gui", action="store_true", help="Forzar modo gráfico")
        
        args = parser.parse_args()

        if args.gui or not args.url:
            # CASO 2: Usuario pidió GUI o no dio URL -> Auto-lanzar Streamlit
            print("🖥️  Lanzando interfaz gráfica...")
            # Truco: El script se llama a sí mismo pero usando 'streamlit run'
            sys.argv = ["streamlit", "run", __file__]
            sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", __file__]))
        else:
            # CASO 3: Modo CLI Clásico
            print("📟 Modo Terminal activado")
            asyncio.run(ejecutar_crawling(args.url, args.output))
