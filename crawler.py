import os
import sys
import asyncio
import argparse
import subprocess
from datetime import datetime
from urllib.parse import urlparse, urljoin

# Importamos Streamlit de forma segura
try:
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except ImportError:
    st = None

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
from crawl4ai.async_dispatcher import SemaphoreDispatcher
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Extensiones de archivo a excluir del crawling
EXTENSIONES_EXCLUIDAS = {
    '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv',
    '.exe', '.dmg', '.deb', '.rpm',
}


def crear_browser_config():
    """Configuración anti-detección del navegador."""
    return BrowserConfig(
        headless=True,
        verbose=False,
        user_agent_mode="random",
        headers={
            "Referer": "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        },
    )


def crear_run_config(modo="static", md_generator=None, **kwargs):
    """Crea la configuración de ejecución según el modo seleccionado."""
    base_params = dict(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=md_generator,
        stream=False,
        page_timeout=60000,
        delay_before_return_html=2.0,
        # Esperar a que la página tenga contenido real
        wait_for="css:body",
        # Anti-detección avanzada
        simulate_user=True,
        override_navigator=True,
        magic=True,
        # Limpieza automática de overlays
        remove_overlay_elements=True,
        # Capturar contenido de iframes
        process_iframes=True,
    )

    if modo == "scroll":
        from crawl4ai import VirtualScrollConfig

        scroll_count = kwargs.get("scroll_count", 20)
        base_params["virtual_scroll_config"] = VirtualScrollConfig(
            container_selector="main, [role='main'], body",
            scroll_count=scroll_count,
            scroll_by="container_height",
            wait_after_scroll=1.5,
        )

    return CrawlerRunConfig(**base_params)


def filtrar_urls(urls_raw, base_url):
    """Filtra URLs: normaliza, elimina fragments, excluye binarios."""
    base_parsed = urlparse(base_url)
    urls_limpias = set()

    for link in urls_raw:
        href = link.get("href", "")
        if not href:
            continue

        # Normalizar URL relativa a absoluta
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Solo mismo dominio y bajo el mismo path base
        if parsed.netloc != base_parsed.netloc:
            continue
        if not parsed.path.startswith(base_parsed.path):
            continue

        # Excluir extensiones binarias
        extension = ""
        if '.' in parsed.path.split('/')[-1]:
            extension = '.' + parsed.path.rsplit('.', 1)[-1].lower()
        if extension in EXTENSIONES_EXCLUIDAS:
            continue

        # Quitar fragment (#) y normalizar
        url_limpia = parsed._replace(fragment="").geturl()
        urls_limpias.add(url_limpia)

    return urls_limpias


async def crawl_con_load_more(crawler, url, run_cfg, selector, max_clicks, log_callback):
    """Modo Load More: clickea el botón repetidamente en la misma sesión."""
    session = "loadmore_session"

    # Paso 1: Carga inicial
    config_inicial = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=run_cfg.markdown_generator,
        stream=False,
        page_timeout=60000,
        delay_before_return_html=2.0,
        wait_for="css:body",
        simulate_user=True,
        override_navigator=True,
        magic=True,
        remove_overlay_elements=True,
        process_iframes=True,
        session_id=session,
    )

    result = await crawler.arun(url=url, config=config_inicial)
    if not result.success:
        return result

    # Paso 2: Click repetido en el botón "Load More"
    js_click = f"""
    (function() {{
        const selectors = '{selector}'.split(',').map(s => s.trim());
        for (const sel of selectors) {{
            const btn = document.querySelector(sel);
            if (btn) {{
                btn.scrollIntoView();
                btn.click();
                return true;
            }}
        }}
        return false;
    }})();
    """

    for i in range(max_clicks):
        log_callback(f"🖱️  Click #{i + 1} en botón 'Load More'...")

        config_click = CrawlerRunConfig(
            session_id=session,
            js_code=js_click,
            wait_for="js:() => { return new Promise(r => setTimeout(() => r(true), 2000)); }",
            js_only=True,
            cache_mode=CacheMode.BYPASS,
            markdown_generator=run_cfg.markdown_generator,
            process_iframes=True,
        )

        result = await crawler.arun(url=url, config=config_click)
        if not result.success:
            log_callback(f"⚠️ Click #{i + 1} falló, deteniendo.")
            break

    # Limpiar sesión
    try:
        await crawler.crawler_strategy.kill_session(session)
    except Exception:
        pass

    return result


async def ejecutar_crawling(url, output_file, modo="static", log_callback=print, **kwargs):
    """Lógica central de crawling con múltiples modos de interacción."""
    domain = url.split("//")[-1].split("/")[0]
    log_callback(f"🚀 Iniciando misión en: {url}")
    log_callback(f"📋 Modo: {modo}")

    # 1. Configuración del Filtro de contenido
    filtro_limpieza = PruningContentFilter(
        threshold=0.48,
        threshold_type="dynamic",
        min_word_threshold=5,
    )
    generador_md = DefaultMarkdownGenerator(content_filter=filtro_limpieza)

    # 2. Configuración del Navegador
    browser_cfg = crear_browser_config()

    # 3. Configuración de ejecución según modo
    run_cfg = crear_run_config(modo=modo, md_generator=generador_md, **kwargs)

    max_concurrent = kwargs.get("max_concurrent", 5)
    lm_selector = kwargs.get("load_more_selector", "button.load-more, a.load-more, [data-load-more]")
    lm_clicks = kwargs.get("load_more_clicks", 10)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        # PASO A: Indexar la página principal
        log_callback("🔍 Escaneando índice...")

        if modo == "loadmore":
            # En modo loadmore, la página principal se crawlea interactivamente
            result_index = await crawl_con_load_more(
                crawler, url, run_cfg, lm_selector, lm_clicks, log_callback
            )
        else:
            result_index = await crawler.arun(url=url, config=run_cfg)

        if not result_index.success:
            log_callback(f"❌ Error crítico: {result_index.error_message}")
            return False

        # PASO B: Filtrar enlaces internos
        urls_encontradas = {url}
        urls_internas = filtrar_urls(
            result_index.links.get("internal", []), url
        )
        urls_encontradas.update(urls_internas)

        # No re-crawlear la URL principal
        urls_a_descargar = list(urls_encontradas - {url})
        log_callback(
            f"✅ Encontradas {len(urls_a_descargar) + 1} páginas. "
            f"Descargando con concurrencia máx. {max_concurrent}..."
        )

        # PASO C: Descarga masiva con límite de concurrencia
        dispatcher = SemaphoreDispatcher(semaphore_count=max_concurrent)
        resultados_principales = []
        if urls_a_descargar:
            resultados_principales = await crawler.arun_many(
                urls_a_descargar,
                config=run_cfg,
                dispatcher=dispatcher,
            )

        # PASO D: Reintentar URLs fallidas (1 intento)
        fallidas = [res.url for res in resultados_principales if not res.success]
        resultados_reintentos = []
        if fallidas:
            log_callback(f"🔄 Reintentando {len(fallidas)} URLs fallidas...")
            resultados_reintentos = await crawler.arun_many(
                fallidas,
                config=run_cfg,
                dispatcher=dispatcher,
            )

        # PASO E: Consolidar y guardar
        log_callback("💾 Consolidando archivo...")

        # Combinar todos los resultados exitosos
        todos_los_resultados = [result_index]
        for res in resultados_principales:
            if res.success:
                todos_los_resultados.append(res)
            else:
                # Buscar en reintentos
                reintento = next(
                    (r for r in resultados_reintentos if r.url == res.url and r.success),
                    None,
                )
                if reintento:
                    todos_los_resultados.append(reintento)
                else:
                    log_callback(f"⚠️ Falló definitivamente: {res.url}")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Documentación de {domain}\n")
            f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"Modo de crawling: {modo}\n\n")

            for res in todos_los_resultados:
                if res.success and res.markdown and res.markdown.fit_markdown:
                    f.write(f"\n\n---\n## FUENTE: {res.url}\n---\n\n")
                    f.write(res.markdown.fit_markdown)

        log_callback(f"🎉 ¡Éxito! Archivo guardado: {output_file}")
        log_callback(f"📊 Páginas procesadas: {len(todos_los_resultados)}")
        return True


# --- LÓGICA DE INTERFAZ GRÁFICA (GUI) ---
def run_gui():
    st.set_page_config(page_title="Omni-Crawler", page_icon="🕷️")
    st.title("🕷️ Omni-Crawler")
    st.markdown("Extractor de documentación para IA (Powered by Crawl4AI)")

    with st.form("crawler_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            url_input = st.text_input(
                "URL de Documentación",
                placeholder="https://caddyserver.com/docs/",
            )
        with col2:
            filename = st.text_input("Nombre Archivo", value="docs.md")

        modo = st.selectbox(
            "Modo de Crawling",
            ["static", "loadmore", "scroll"],
            format_func=lambda m: {
                "static": "📄 Estático (páginas normales)",
                "loadmore": "🖱️ Load More (botón 'Ver más')",
                "scroll": "📜 Scroll Infinito",
            }[m],
        )

        # Campos condicionales según modo
        lm_selector = ""
        lm_clicks = 10
        scroll_count = 20
        max_concurrent = 5

        if modo == "loadmore":
            lm_selector = st.text_input(
                "CSS Selector del botón",
                value="button.load-more, a.load-more, [data-load-more]",
            )
            lm_clicks = st.slider("Máx. clicks", 1, 50, 10)

        if modo == "scroll":
            scroll_count = st.slider("Cantidad de scrolls", 5, 100, 20)

        max_concurrent = st.slider("Concurrencia máxima", 1, 20, 5)

        submitted = st.form_submit_button("🚀 Iniciar Extracción")

    log_container = st.empty()

    def gui_logger(msg):
        if "❌" in msg:
            log_container.error(msg)
        elif "✅" in msg or "🎉" in msg:
            log_container.success(msg)
        else:
            log_container.info(msg)

    if submitted and url_input:
        asyncio.run(
            ejecutar_crawling(
                url_input,
                filename,
                modo=modo,
                log_callback=gui_logger,
                load_more_selector=lm_selector,
                load_more_clicks=lm_clicks,
                scroll_count=scroll_count,
                max_concurrent=max_concurrent,
            )
        )

        if os.path.exists(filename):
            with open(filename, "r") as f:
                st.download_button("📥 Bajar Markdown", f, file_name=filename)


# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    is_running_as_streamlit = False
    try:
        if get_script_run_ctx():
            is_running_as_streamlit = True
    except Exception:
        pass

    if is_running_as_streamlit:
        run_gui()
    else:
        parser = argparse.ArgumentParser(
            description="🕷️ Omni-Crawler: Extractor de documentación para IA",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Ejemplos:
  %(prog)s https://docs.ejemplo.com/ -o docs.md
  %(prog)s https://sitio.com/blog --mode loadmore --load-more-selector "button.more"
  %(prog)s https://sitio.com/feed --mode scroll --scroll-count 30
            """,
        )
        parser.add_argument("url", nargs="?", help="URL a procesar")
        parser.add_argument("-o", "--output", default="output.md", help="Archivo de salida (default: output.md)")
        parser.add_argument("--gui", action="store_true", help="Forzar modo gráfico")
        parser.add_argument(
            "--mode",
            choices=["static", "loadmore", "scroll"],
            default="static",
            help="Modo de crawling: static (default), loadmore (botón 'Ver más'), scroll (infinite scroll)",
        )
        parser.add_argument(
            "--load-more-selector",
            default="button.load-more, a.load-more, [data-load-more]",
            help="CSS selector del botón 'Load More' (solo en modo loadmore)",
        )
        parser.add_argument(
            "--load-more-clicks",
            type=int,
            default=10,
            help="Máximo de clicks en 'Load More' (default: 10)",
        )
        parser.add_argument(
            "--scroll-count",
            type=int,
            default=20,
            help="Número de scrolls en modo scroll (default: 20)",
        )
        parser.add_argument(
            "--max-concurrent",
            type=int,
            default=5,
            help="Máximo de páginas descargadas simultáneamente (default: 5)",
        )

        args = parser.parse_args()

        if args.gui or not args.url:
            print("🖥️  Lanzando interfaz gráfica...")
            sys.argv = ["streamlit", "run", __file__]
            sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", __file__]))
        else:
            print("📟 Modo Terminal activado")
            asyncio.run(
                ejecutar_crawling(
                    args.url,
                    args.output,
                    modo=args.mode,
                    load_more_selector=args.load_more_selector,
                    load_more_clicks=args.load_more_clicks,
                    scroll_count=args.scroll_count,
                    max_concurrent=args.max_concurrent,
                )
            )