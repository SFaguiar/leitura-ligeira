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
import ssl
import zipfile
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse

import ebooklib
import pymupdf
import trafilatura
import urllib3
from ebooklib import epub

MAX_URL_BYTES = 10 * 1024 * 1024
MAX_URL_REDIRECTS = 3
MAX_EPUB_ENTRIES = 5_000
MAX_EPUB_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
_ALLOWED_URL_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})


def validate_upload(filename: str, content_type: str | None, raw: bytes) -> str:
    name = filename.strip()
    if (
        not name
        or len(name) > 255
        or "/" in name
        or "\\" in name
        or any(ord(char) < 32 for char in name)
    ):
        raise ValueError("Nome de arquivo inválido.")
    suffix = name.rsplit(".", 1)[-1].casefold() if "." in name else ""
    media_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().casefold()
    allowed_types = {
        "pdf": {"application/pdf", "application/octet-stream"},
        "epub": {"application/epub+zip", "application/zip", "application/octet-stream"},
        "txt": {"text/plain", "application/octet-stream"},
    }
    if suffix not in allowed_types or media_type not in allowed_types[suffix]:
        raise ValueError("Tipo ou extensão de arquivo não permitido.")
    if suffix == "pdf" and not raw.startswith(b"%PDF-"):
        raise ValueError("O conteúdo não possui uma assinatura PDF válida.")
    if suffix == "epub":
        _validate_epub_container(raw)
    if suffix == "txt" and b"\x00" in raw:
        raise ValueError("O TXT parece conter dados binários.")
    return suffix


def _validate_epub_container(file_bytes: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_EPUB_ENTRIES:
                raise ValueError("EPUB possui arquivos internos demais.")
            total = 0
            for entry in entries:
                normalized = entry.filename.replace("\\", "/")
                parts = [part for part in normalized.split("/") if part]
                if normalized.startswith("/") or ".." in parts:
                    raise ValueError("EPUB contém caminho interno inseguro.")
                total += entry.file_size
                if total > MAX_EPUB_UNCOMPRESSED_BYTES:
                    raise ValueError("EPUB descompactado excede o limite seguro.")
            try:
                mimetype = archive.read("mimetype", pwd=None)
            except KeyError as exc:
                raise ValueError("EPUB não contém o marcador obrigatório.") from exc
            if mimetype.strip() != b"application/epub+zip":
                raise ValueError("Marcador de formato EPUB inválido.")
    except zipfile.BadZipFile as exc:
        raise ValueError("EPUB inválido ou corrompido.") from exc


def extract_pdf(file_bytes: bytes) -> tuple[str, list[dict] | None]:
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("PDF inválido ou corrompido.") from exc

    try:
        if doc.page_count > 10_000:
            raise ValueError("PDF possui páginas demais para processamento seguro.")
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
    finally:
        doc.close()

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


def _check_not_loopback(hostname: str) -> tuple[str, ...]:
    # Resolves the hostname and checks the actual IP — not a string match on
    # "localhost"/"127.0.0.1", which decimal/octal/alternate encodings could
    # bypass. Known accepted gap: does not re-check redirect targets, and is
    # vulnerable to DNS rebinding (re-resolution at connect time could differ)
    # — acceptable for this project's threat model (trusted household
    # accounts on a LAN, not adversarial external actors).
    # R6 closes the historical gap documented above: every redirect is checked
    # and the HTTP client connects to one of these exact validated IPs.
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Não foi possível resolver esse domínio.") from exc
    addresses = tuple(sorted({sockaddr[0] for *_prefix, sockaddr in infos}))
    if not addresses:
        raise ValueError("O domínio não retornou um endereço utilizável.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("O domínio retornou um endereço inválido.") from exc
        if not ip.is_global:
            raise ValueError("URLs para redes locais, reservadas ou de metadados não são permitidas.")
    return addresses


def _validated_url(url: str, previous_scheme: str | None = None):
    if not isinstance(url, str) or not 1 <= len(url) <= 2048:
        raise ValueError("URL inválida ou longa demais.")
    if any(ord(char) < 32 for char in url):
        raise ValueError("URL contém caracteres de controle.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL inválida — use http:// ou https://.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs com credenciais embutidas não são permitidas.")
    if previous_scheme == "https" and parsed.scheme != "https":
        raise ValueError("Redirecionamento de HTTPS para HTTP não é permitido.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("Porta da URL inválida.") from exc
    if port not in {80, 443}:
        raise ValueError("A importação por URL aceita somente as portas 80 e 443.")
    try:
        hostname = parsed.hostname.encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise ValueError("Domínio internacional inválido.") from exc
    addresses = _check_not_loopback(hostname)
    display_host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = display_host if port == default_port else f"{display_host}:{port}"
    normalized = urlunparse(
        (parsed.scheme, netloc, parsed.path or "/", "", parsed.query, "")
    )
    return urlparse(normalized), addresses[0], normalized


def _fetch_once(url: str, previous_scheme: str | None = None):
    parsed, address, normalized = _validated_url(url, previous_scheme)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    hostname = parsed.hostname or ""
    timeout = urllib3.Timeout(connect=5.0, read=15.0)
    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            address,
            port=port,
            timeout=timeout,
            maxsize=1,
            block=True,
            retries=False,
            cert_reqs=ssl.CERT_REQUIRED,
            assert_hostname=hostname,
            server_hostname=hostname,
        )
    else:
        pool = urllib3.HTTPConnectionPool(
            address,
            port=port,
            timeout=timeout,
            maxsize=1,
            block=True,
            retries=False,
        )
    default_port = 443 if parsed.scheme == "https" else 80
    display_host = f"[{hostname}]" if ":" in hostname else hostname
    host_header = display_host if port == default_port else f"{display_host}:{port}"
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    response = None
    try:
        response = pool.request(
            "GET",
            target,
            headers={
                "Host": host_header,
                "User-Agent": "LeituraLigeira/1.0 (self-hosted reader)",
                "Accept": "text/html, application/xhtml+xml, text/plain;q=0.8",
                "Accept-Encoding": "identity",
            },
            redirect=False,
            preload_content=False,
            retries=False,
        )
        headers = dict(response.headers.items())
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise ValueError("O site retornou um tamanho de resposta inválido.") from exc
            if declared_length < 0:
                raise ValueError("O site retornou um tamanho de resposta inválido.")
            if declared_length > MAX_URL_BYTES:
                raise ValueError("Página muito grande para importar.")
        raw = b"" if response.status in {301, 302, 303, 307, 308} else response.read(MAX_URL_BYTES + 1)
        if len(raw) > MAX_URL_BYTES:
            raise ValueError("Página muito grande para importar.")
        return response.status, headers, raw, normalized
    except urllib3.exceptions.HTTPError as exc:
        raise ValueError("Não foi possível estabelecer uma conexão segura com esse site.") from exc
    finally:
        if response is not None:
            response.release_conn()
        pool.close()


def _response_charset(content_type: str) -> str:
    for part in content_type.split(";")[1:]:
        key, separator, value = part.partition("=")
        if separator and key.strip().casefold() == "charset":
            candidate = value.strip().strip('"').strip("'")
            if 1 <= len(candidate) <= 40 and candidate.isascii():
                return candidate
    return "utf-8"


def extract_url(url: str) -> tuple[str, str | None]:
    current = url
    previous_scheme = None
    for redirect_count in range(MAX_URL_REDIRECTS + 1):
        status, headers, raw, final_url = _fetch_once(current, previous_scheme)
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("Location") or headers.get("location")
            if not location or redirect_count >= MAX_URL_REDIRECTS:
                raise ValueError("O site excedeu o limite seguro de redirecionamentos.")
            previous_scheme = urlparse(final_url).scheme
            current = urljoin(final_url, location)
            continue
        if status != 200:
            raise ValueError(f"O site respondeu HTTP {status}; não foi possível importar.")
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        media_type = content_type.split(";", 1)[0].strip().casefold()
        if media_type not in _ALLOWED_URL_TYPES:
            raise ValueError("A URL não retornou uma página de texto permitida.")
        charset = _response_charset(content_type)
        try:
            html = raw.decode(charset, errors="replace")
        except LookupError:
            html = raw.decode("utf-8", errors="replace")
        break
    else:
        raise ValueError("O site excedeu o limite seguro de redirecionamentos.")

    text = trafilatura.extract(html, url=final_url)
    if not text or not text.strip():
        raise ValueError(
            "Não foi possível extrair o conteúdo dessa página — pode exigir "
            "JavaScript ou ter pouco texto reconhecível."
        )

    metadata = trafilatura.extract_metadata(html, default_url=final_url)
    page_title = metadata.title if metadata and metadata.title else None

    return text, page_title
