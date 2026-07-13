"""Text + TOC extraction for PDF/EPUB uploads and URL imports (Fase 6).

Token indices in the returned TOC are word counts (`str.split()`), computed
directly during extraction — never derived from a character offset. PDF
outlines only give a page number (no in-page position), and EPUB TOC entries
correspond to whole spine files in the common case, so counting words
cumulatively per page/chapter sidesteps ever landing mid-word, which a
char-offset-based conversion could not guarantee.
"""

import io
import ipaddress
import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

import ebooklib
import pymupdf
import trafilatura
from ebooklib import epub

MAX_URL_BYTES = 10 * 1024 * 1024


def extract_pdf(file_bytes: bytes) -> tuple[str, list[dict] | None]:
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("PDF inválido ou corrompido.") from exc

    page_texts = [page.get_text() for page in doc]
    full_text = "\n".join(page_texts)
    if not full_text.strip():
        raise ValueError(
            "Não foi possível extrair texto deste PDF — provavelmente é um "
            "documento escaneado (imagem), sem suporte a OCR."
        )

    # Cumulative word count before each page — the TOC's page-level
    # granularity means a chapter jump snaps to the start of its page, not
    # the exact heading line within it.
    cumulative_words = [0]
    for text in page_texts:
        cumulative_words.append(cumulative_words[-1] + len(text.split()))

    toc = []
    for _level, title, page_num in doc.get_toc():
        idx = max(0, min(page_num - 1, len(page_texts)))
        toc.append({"title": title, "token_index": cumulative_words[idx]})

    return full_text, (toc or None)


_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr", "blockquote"}
_SKIP_TAGS = {"script", "style", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self.skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n[ \t\n]*", "\n\n", text)
    return text.strip()


def extract_epub(file_bytes: bytes) -> tuple[str, list[dict] | None]:
    try:
        book = epub.read_epub(io.BytesIO(file_bytes), options={"ignore_ncx": True})
    except Exception as exc:
        raise ValueError("EPUB inválido ou corrompido.") from exc

    # Spine order is reading order; EpubNav/EpubCoverHtml share the same
    # ITEM_DOCUMENT type code as real chapters but aren't content.
    chapters: list[tuple[str, str]] = []
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None or isinstance(item, (epub.EpubNav, epub.EpubCoverHtml)):
            continue
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        html = item.get_content().decode("utf-8", errors="replace")
        text = _html_to_text(html)
        if text:
            chapters.append((item.get_name(), text))

    if not chapters:
        raise ValueError("Não foi possível extrair texto deste EPUB.")

    cumulative_words = [0]
    name_to_cum = {}
    for name, text in chapters:
        name_to_cum[name] = cumulative_words[-1]
        cumulative_words.append(cumulative_words[-1] + len(text.split()))

    full_text = "\n\n".join(text for _, text in chapters)

    toc: list[dict] = []

    def _add(title, href):
        # A TOC entry pointing at a sub-section anchor within a spine file
        # (single-file EPUBs) snaps to that file's start — sub-chapter
        # granularity isn't tracked. Accepted simplification (YAGNI).
        if not href or not title:
            return
        file_part = href.split("#")[0]
        idx = name_to_cum.get(file_part)
        if idx is not None:
            toc.append({"title": title, "token_index": idx})

    def _walk(entries):
        for entry in entries:
            if isinstance(entry, tuple):
                section = entry[0]
                children = entry[1] if len(entry) > 1 else []
                _add(getattr(section, "title", None), getattr(section, "href", None))
                _walk(children)
            else:
                _add(getattr(entry, "title", None), getattr(entry, "href", None))

    _walk(book.toc)

    return full_text, (toc or None)


def _check_not_loopback(hostname: str) -> None:
    # Resolves the hostname and checks the actual IP — not a string match on
    # "localhost"/"127.0.0.1", which decimal/octal/alternate encodings could
    # bypass. Known accepted gap: does not re-check redirect targets, and is
    # vulnerable to DNS rebinding (re-resolution at connect time could differ)
    # — acceptable for this project's threat model (trusted household
    # accounts on a LAN, not adversarial external actors).
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError("Não foi possível resolver esse domínio.") from exc
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_loopback:
            raise ValueError("URLs apontando para localhost não são permitidas.")


def extract_url(url: str) -> tuple[str, str | None]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL inválida — use http:// ou https://.")
    _check_not_loopback(parsed.hostname)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; LeituraLigeira/1.0; self-hosted reader)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read(MAX_URL_BYTES + 1)
            if len(raw) > MAX_URL_BYTES:
                raise ValueError("Página muito grande para importar.")
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"O site respondeu com erro {exc.code} — pode ser paywall ou bloqueio.") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Não foi possível acessar essa URL: {exc.reason}") from exc

    text = trafilatura.extract(html, url=url)
    if not text or not text.strip():
        raise ValueError(
            "Não foi possível extrair o conteúdo dessa página — pode exigir "
            "JavaScript ou ter pouco texto reconhecível."
        )

    metadata = trafilatura.extract_metadata(html, default_url=url)
    page_title = metadata.title if metadata and metadata.title else None

    return text, page_title
