"""
Modulo A — Web Scraping & Indexacao do Spriters Resource (Ragnarok Online).

O site www.spriters-resource.com fica atras da protecao Cloudflare, que
bloqueia clientes HTTP simples (requests/urllib recebem HTTP 403). Por isso a
estrategia deste modulo e' em duas camadas:

  1. Tentativa rapida com `requests` + cabecalhos de navegador (funciona em
     algumas redes/regioes).
  2. Fallback com Playwright (Chromium real, headless), que executa o
     JavaScript do Cloudflare e obtem a pagina como um navegador de verdade.
     O download dos PNGs reaproveita os cookies da mesma sessao do navegador.

O resultado do mapeamento vira um indice local em JSON
(`data/sprite_index.json`) para que as buscas seguintes sejam instantaneas e
o site nao seja consultado repetidamente (scraping educado).
"""

from __future__ import annotations

import difflib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from keywords import _strip_accents, translate_query

BASE_URL = "https://www.spriters-resource.com"
GAME_URL = f"{BASE_URL}/pc_computer/ragnarokonline/"

DATA_DIR = Path(__file__).parent / "data"
INDEX_FILE = DATA_DIR / "sprite_index.json"
DOWNLOAD_DIR = DATA_DIR / "downloads"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
    "Referer": BASE_URL + "/",
}


@dataclass
class SheetEntry:
    """Uma entrada do indice: um spritesheet disponivel no site."""

    sheet_id: str
    name: str
    url: str
    section: str = ""
    thumbnail: str = ""


# ---------------------------------------------------------------------------
# Camada de acesso HTTP (requests -> Playwright)
# ---------------------------------------------------------------------------

class SpritersClient:
    """Cliente HTTP que tenta `requests` e cai para Playwright se bloqueado."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._cloudscraper = None

    # -- requests -----------------------------------------------------------

    def _try_requests(self, url: str) -> str | None:
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
            if resp.status_code == 200 and "cf-challenge" not in resp.text[:2000].lower():
                return resp.text
        except requests.RequestException:
            pass
        return None

    def _try_requests_bytes(self, url: str) -> bytes | None:
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=60)
            if resp.status_code == 200 and _e_imagem(resp.content):
                return resp.content
        except requests.RequestException:
            pass
        return None

    # -- cloudscraper (resolve desafios Cloudflare sem navegador) -----------

    def _get_cloudscraper(self):
        if self._cloudscraper is None:
            try:
                import cloudscraper

                self._cloudscraper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "desktop": True}
                )
            except Exception:
                self._cloudscraper = False  # indisponivel
        return self._cloudscraper or None

    def _try_cloudscraper(self, url: str) -> str | None:
        scraper_session = self._get_cloudscraper()
        if scraper_session is None:
            return None
        try:
            resp = scraper_session.get(url, timeout=45)
            if resp.status_code == 200 and "/sheet/" in resp.text:
                return resp.text
        except Exception:
            pass
        return None

    def _try_cloudscraper_bytes(self, url: str) -> bytes | None:
        scraper_session = self._get_cloudscraper()
        if scraper_session is None:
            return None
        try:
            resp = scraper_session.get(url, timeout=60)
            if resp.status_code == 200 and _e_imagem(resp.content):
                return resp.content
        except Exception:
            pass
        return None

    # -- Playwright ---------------------------------------------------------

    def _ensure_browser(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        # O sandbox do Chromium e' uma camada de defesa real ao abrir um site
        # externo. So' e' desligado quando o ambiente impede seu uso (rodando
        # como root em container), nunca na maquina do usuario.
        args = ["--disable-blink-features=AutomationControlled"]
        if _precisa_desligar_sandbox():
            args.append("--no-sandbox")
        launch_kwargs = dict(headless=self.headless, args=args)
        try:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
        except Exception:
            # Em hospedagem na nuvem (ex.: Streamlit Community Cloud) o
            # navegador do Playwright nunca foi baixado. Instala uma unica
            # vez e tenta de novo.
            import subprocess
            import sys

            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
                capture_output=True,
                timeout=600,
            )
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            user_agent=BROWSER_HEADERS["User-Agent"],
            locale="en-US",
            viewport={"width": 1366, "height": 900},
        )
        # "Stealth": esconde os sinais de automacao que o Cloudflare procura.
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            "window.chrome = window.chrome || {runtime: {}};"
            "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'pt-BR']});"
            "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});"
        )
        self._page = self._context.new_page()

    def _playwright_html(self, url: str) -> str:
        self._ensure_browser()
        self._page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        # Da tempo ao desafio do Cloudflare ("Just a moment...") de resolver.
        for _ in range(45):
            title = (self._page.title() or "").lower()
            if "just a moment" not in title and "attention required" not in title:
                break
            time.sleep(1)
        return self._page.content()

    def _playwright_bytes(self, url: str) -> bytes:
        """Baixa um binario reaproveitando os cookies da sessao do navegador."""
        self._ensure_browser()
        resp = self._context.request.get(url, timeout=60_000)
        if not resp.ok:
            raise RuntimeError(f"Download falhou ({resp.status}): {url}")
        return resp.body()

    # -- API publica --------------------------------------------------------

    def get_html(self, url: str) -> str:
        html = self._try_requests(url)
        if html:
            return html
        html = self._try_cloudscraper(url)
        if html:
            return html
        return self._playwright_html(url)

    def get_bytes(self, url: str) -> bytes:
        data = self._try_requests_bytes(url)
        if data:
            return data
        data = self._try_cloudscraper_bytes(url)
        if data:
            return data
        return self._playwright_bytes(url)

    def close(self):
        # A sessao do cloudscraper tambem mantem conexoes abertas.
        sessao = getattr(self, "_cloudscraper", None)
        if sessao:
            try:
                sessao.close()
            except Exception:
                pass
        self._cloudscraper = None

        for obj in (self._context, self._browser):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._playwright = self._browser = self._context = self._page = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ---------------------------------------------------------------------------
# Indexacao
# ---------------------------------------------------------------------------

def _e_imagem(dados: bytes) -> bool:
    """Reconhece PNG, GIF, JPEG e WEBP pela assinatura dos primeiros bytes."""
    if not dados or len(dados) < 12:
        return False
    return (
        dados.startswith(b"\x89PNG")
        or dados[:3] == b"GIF"
        or dados[:2] == b"\xff\xd8"
        or (dados[:4] == b"RIFF" and dados[8:12] == b"WEBP")
    )


def _precisa_desligar_sandbox() -> bool:
    """
    O sandbox do Chromium nao funciona rodando como root (caso tipico de
    container/nuvem). Fora disso ele fica LIGADO, preservando o isolamento.
    """
    try:
        return hasattr(os, "geteuid") and os.geteuid() == 0
    except Exception:
        return False


ALLOWED_HOSTS = {
    "spriters-resource.com",
    "www.spriters-resource.com",
    "cdn.spriters-resource.com",
}


def _url_permitida(url: str) -> bool:
    """
    So permite baixar de dominios do Spriters Resource.

    As URLs candidatas sao extraidas do HTML do site, ou seja, sao conteudo de
    terceiros: sem esta barreira, um link malicioso (ou apenas um anuncio)
    faria o app requisitar um host arbitrario a partir do servidor.
    """
    try:
        partes = urlparse(url)
    except ValueError:
        return False
    if partes.scheme not in ("http", "https"):
        return False
    return partes.hostname in ALLOWED_HOSTS


def _page_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip()[:80] if match else "(sem titulo)"

def _parse_game_page(html: str) -> list[SheetEntry]:
    """
    Extrai todos os links de spritesheets da pagina do jogo.

    Os links seguem o padrao /pc_computer/ragnarokonline/sheet/<id>/ e o texto
    visivel do link (ou o atributo title/alt) e' o nome do sheet. As secoes
    ("Playable Characters", "Monsters"...) aparecem como cabecalhos antes de
    cada bloco de icones.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: list[SheetEntry] = []
    seen: set[str] = set()
    current_section = ""

    # Percorre o documento em ordem para associar cada sheet ao cabecalho
    # de secao mais recente.
    for element in soup.find_all(["h2", "h3", "div", "a"]):
        classes = element.get("class") or []
        if element.name in ("h2", "h3") or "sect-name" in classes:
            text = element.get_text(strip=True)
            if text:
                current_section = text
            continue

        if element.name != "a":
            continue
        href = element.get("href") or ""
        match = re.search(r"/sheet/(\d+)/?", href)
        if not match:
            continue
        sheet_id = match.group(1)
        if sheet_id in seen:
            continue

        name = element.get_text(" ", strip=True) or element.get("title", "")
        img = element.find("img")
        thumbnail = ""
        if img is not None:
            thumbnail = img.get("src") or ""
            if not name:
                name = img.get("alt", "")
        if not name:
            continue

        if thumbnail.startswith("/"):
            thumbnail = BASE_URL + thumbnail

        seen.add(sheet_id)
        entries.append(
            SheetEntry(
                sheet_id=sheet_id,
                name=name.strip(),
                url=f"{BASE_URL}/pc_computer/ragnarokonline/sheet/{sheet_id}/",
                section=current_section,
                thumbnail=thumbnail,
            )
        )
    return entries


def _carregar_indice() -> list[SheetEntry]:
    """
    Le o indice do disco tolerando arquivo corrompido ou de versao antiga.

    Devolve lista vazia quando nao da' para aproveitar — quem chama trata isso
    reconstruindo o indice, em vez de propagar a excecao para a interface.
    """
    campos = {f.name for f in fields(SheetEntry)}
    try:
        raw = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        entradas = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            # Ignora chaves desconhecidas (indice gravado por outra versao)
            filtrado = {k: v for k, v in item.items() if k in campos}
            if "sheet_id" in filtrado and "name" in filtrado and "url" in filtrado:
                entradas.append(SheetEntry(**filtrado))
        return entradas
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return []


def _gravar_indice(entries: list[SheetEntry]) -> None:
    """
    Grava o indice de forma atomica (arquivo temporario + rename).

    Se o processo for interrompido no meio da escrita, o indice antigo
    permanece intacto em vez de virar um arquivo pela metade.
    """
    conteudo = json.dumps(
        [asdict(e) for e in entries], ensure_ascii=False, indent=2
    )
    temporario = INDEX_FILE.with_suffix(".json.tmp")
    temporario.write_text(conteudo, encoding="utf-8")
    temporario.replace(INDEX_FILE)


def build_index(force: bool = False, client: SpritersClient | None = None) -> list[SheetEntry]:
    """
    Constroi (ou carrega do cache) o indice local de sprites.

    O indice fica salvo em data/sprite_index.json. So volta ao site se o
    arquivo nao existir ou se `force=True`.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if INDEX_FILE.exists() and not force:
        entradas = _carregar_indice()
        if entradas:
            return entradas
        # Indice ilegivel (corrompido, truncado ou de uma versao antiga):
        # segue adiante e reconstroi, em vez de derrubar o app.

    own_client = client is None
    client = client or SpritersClient()
    try:
        html = client.get_html(GAME_URL)
        entries = _parse_game_page(html)
        if not entries:
            lower = html.lower()
            if any(
                marker in lower
                for marker in (
                    "just a moment", "attention required", "cf-challenge",
                    "challenge-platform", "verify you are human", "cloudflare",
                )
            ):
                raise RuntimeError(
                    "BLOQUEIO DO CLOUDFLARE: o site recusou o acesso a partir "
                    "deste servidor (IPs de nuvem/datacenter costumam ser "
                    "barrados). A busca automatica funciona rodando o app no "
                    "seu computador; na nuvem, use a aba de upload manual."
                )
            raise RuntimeError(
                "Nenhum sheet encontrado na pagina — o layout do site pode "
                "ter mudado. Abra uma issue ou use a aba de upload manual. "
                f"(titulo da pagina recebida: {_page_title(html)!r})"
            )
        _gravar_indice(entries)
        return entries
    finally:
        if own_client:
            client.close()


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

def search_sheets(query: str, entries: list[SheetEntry], limit: int = 12) -> list[SheetEntry]:
    """
    Busca por relevancia: traduz o pedido PT->EN (keywords.py) e pontua cada
    entrada do indice por correspondencia exata, parcial e aproximada (fuzzy).
    """
    terms = translate_query(query)
    if not terms:
        return []

    scored: list[tuple[float, SheetEntry]] = []
    for entry in entries:
        name_clean = _strip_accents(entry.name)
        score = 0.0
        for i, term in enumerate(terms):
            weight = 1.0 / (1 + i * 0.3)  # termos iniciais valem mais
            if term == name_clean:
                score += 10 * weight
            elif re.search(rf"\b{re.escape(term)}\b", name_clean):
                score += 6 * weight
            elif term in name_clean:
                score += 3 * weight
            else:
                fuzzy = difflib.SequenceMatcher(None, term, name_clean).ratio()
                if fuzzy > 0.75:
                    score += 2 * fuzzy * weight
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


# ---------------------------------------------------------------------------
# Download do spritesheet
# ---------------------------------------------------------------------------

def download_sheet(entry: SheetEntry, client: SpritersClient | None = None) -> Path:
    """
    Baixa o PNG completo de um spritesheet.

    Estrategia:
      1. URL direta conhecida do site: /download/<id>/ (botao "Download").
      2. Se falhar, abre a pagina do sheet e procura a imagem principal
         (/resources/sheets/...) ou o link de download no HTML.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]+", "_", _strip_accents(entry.name)).strip("_")
    target = DOWNLOAD_DIR / f"{entry.sheet_id}_{safe_name}.png"
    if target.exists():
        return target

    own_client = client is None
    client = client or SpritersClient()
    try:
        # 1) Endpoint direto de download
        try:
            data = client.get_bytes(f"{BASE_URL}/download/{entry.sheet_id}/")
            if _e_imagem(data):
                target.write_bytes(data)
                return target
        except Exception:
            pass

        # 2) Pagina do sheet -> localizar a imagem em tamanho real
        html = client.get_html(entry.url)
        soup = BeautifulSoup(html, "html.parser")

        candidates: list[str] = []
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if "/resources/sheets/" in src:
                candidates.append(src)
        for link in soup.find_all("a"):
            href = link.get("href") or ""
            if "/download/" in href or "/resources/sheets/" in href:
                candidates.append(href)

        if not candidates:
            raise RuntimeError(
                f"Nao encontrei a imagem do sheet em {entry.url} — "
                "o layout do site pode ter mudado."
            )

        for src in candidates:
            url = src if src.startswith("http") else BASE_URL + src
            # As URLs vem do HTML de um site de terceiros. Sem esta checagem,
            # um link para outro dominio faria o app buscar um host arbitrario
            # (SSRF) — inclusive enderecos internos da rede onde ele roda.
            if not _url_permitida(url):
                continue
            try:
                data = client.get_bytes(url)
            except Exception:
                continue
            if _e_imagem(data):
                target.write_bytes(data)
                return target

        raise RuntimeError(f"Falha ao baixar a imagem do sheet '{entry.name}'.")
    finally:
        if own_client:
            client.close()


# ---------------------------------------------------------------------------
# Atalho de alto nivel usado pela interface
# ---------------------------------------------------------------------------

def find_and_download(query: str, choice_index: int = 0) -> tuple[SheetEntry, Path]:
    """Busca -> escolhe o resultado `choice_index` -> baixa. Uso via terminal."""
    with SpritersClient() as client:
        entries = build_index(client=client)
        results = search_sheets(query, entries)
        if not results:
            raise LookupError(f"Nenhum sprite encontrado para: {query!r}")
        chosen = results[min(choice_index, len(results) - 1)]
        path = download_sheet(chosen, client=client)
        return chosen, path


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Cavaleiro"
    entry, path = find_and_download(q)
    print(f"[OK] {entry.name} ({entry.url})\n     salvo em: {path}")
