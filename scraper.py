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
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

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
            if resp.status_code == 200 and resp.content[:8].startswith(b"\x89PNG"):
                return resp.content
        except requests.RequestException:
            pass
        return None

    # -- Playwright ---------------------------------------------------------

    def _ensure_browser(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            user_agent=BROWSER_HEADERS["User-Agent"],
            locale="en-US",
        )
        self._page = self._context.new_page()

    def _playwright_html(self, url: str) -> str:
        self._ensure_browser()
        self._page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        # Da tempo ao desafio do Cloudflare ("Just a moment...") de resolver.
        for _ in range(20):
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
        return self._playwright_html(url)

    def get_bytes(self, url: str) -> bytes:
        data = self._try_requests_bytes(url)
        if data:
            return data
        return self._playwright_bytes(url)

    def close(self):
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


def build_index(force: bool = False, client: SpritersClient | None = None) -> list[SheetEntry]:
    """
    Constroi (ou carrega do cache) o indice local de sprites.

    O indice fica salvo em data/sprite_index.json. So volta ao site se o
    arquivo nao existir ou se `force=True`.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if INDEX_FILE.exists() and not force:
        raw = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        return [SheetEntry(**item) for item in raw]

    own_client = client is None
    client = client or SpritersClient()
    try:
        html = client.get_html(GAME_URL)
        entries = _parse_game_page(html)
        if not entries:
            raise RuntimeError(
                "Nenhum sheet encontrado na pagina — o site pode ter mudado "
                "de layout ou o Cloudflare bloqueou o acesso."
            )
        INDEX_FILE.write_text(
            json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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
            if data[:8].startswith(b"\x89PNG"):
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
            try:
                data = client.get_bytes(url)
            except Exception:
                continue
            if data[:8].startswith(b"\x89PNG") or data[:3] == b"GIF" or data[:2] == b"\xff\xd8":
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
