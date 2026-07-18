import argparse
import ipaddress
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uvicorn


DEFAULT_CERT = BASE_DIR / "certs" / "leitura-ligeira.pem"
DEFAULT_KEY = BASE_DIR / "certs" / "leitura-ligeira-key.pem"


@dataclass(frozen=True)
class ExistingServer:
    url: str
    https_enabled: bool
    lan_enabled: bool


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inicia o Leitura Ligeira com transporte seguro opcional.")
    parser.add_argument("--lan", action="store_true", help="Expõe o servidor na rede local (0.0.0.0).")
    parser.add_argument("--host", help="Host explícito. 0.0.0.0 exige também --lan.")
    parser.add_argument("--port", type=int, default=int(os.getenv("LEITURA_PORT", "8000")))
    parser.add_argument("--certfile", type=Path, help="Certificado PEM para habilitar HTTPS.")
    parser.add_argument("--keyfile", type=Path, help="Chave privada PEM correspondente.")
    parser.add_argument("--no-https", action="store_true", help="Ignora certificados padrão/ambiente e usa HTTP.")
    return parser


def _configured_path(argument: Path | None, env_name: str, default: Path) -> Path | None:
    if argument is not None:
        return argument.expanduser().resolve()
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return default.resolve() if default.exists() else None


def _validate_certificate_pair(certfile: Path | None, keyfile: Path | None) -> tuple[Path | None, Path | None]:
    if (certfile is None) != (keyfile is None):
        raise ValueError("HTTPS exige certificado e chave juntos (--certfile e --keyfile).")
    if certfile is None:
        return None, None
    if not certfile.is_file():
        raise ValueError(f"Certificado não encontrado: {certfile}")
    if not keyfile.is_file():
        raise ValueError(f"Chave privada não encontrada: {keyfile}")
    if certfile == keyfile:
        raise ValueError("Certificado e chave privada não podem apontar para o mesmo arquivo.")
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
    except (OSError, ssl.SSLError) as exc:
        raise ValueError(f"Par de certificado/chave inválido: {exc}") from exc
    return certfile, keyfile


def _local_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            return probe.getsockname()[0]
    except OSError:
        return None


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _probe_host(host: str) -> str:
    normalized = host.strip().strip("[]")
    if normalized in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return normalized


def _format_url(scheme: str, host: str, port: int) -> str:
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"{scheme}://{display_host}:{port}"


def _probe_transport(url: str) -> dict | None:
    # Esta sondagem serve apenas para identificar uma instância local já ativa.
    # Ela não transporta credenciais e precisa reconhecer também certificados locais
    # ainda não confiados pelo usuário que executou o launcher.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context),
    )
    request = urllib.request.Request(
        f"{url}/system/transport",
        headers={"User-Agent": "Leitura-Ligeira-Launcher/1.0"},
    )
    try:
        with opener.open(request, timeout=0.7) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read(4096).decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    if payload.get("scheme") not in {"http", "https"}:
        return None
    if not isinstance(payload.get("https"), bool) or not isinstance(payload.get("lan_enabled"), bool):
        return None
    return payload


def _find_existing_server(host: str, port: int, prefer_https: bool) -> ExistingServer | None:
    probe_host = _probe_host(host)
    schemes = ("https", "http") if prefer_https else ("http", "https")
    for scheme in schemes:
        url = _format_url(scheme, probe_host, port)
        payload = _probe_transport(url)
        if payload is not None:
            actual_scheme = payload["scheme"]
            return ExistingServer(
                url=_format_url(actual_scheme, probe_host, port),
                https_enabled=payload["https"],
                lan_enabled=payload["lan_enabled"],
            )
    return None


def _port_is_available(host: str, port: int) -> bool:
    normalized = host.strip().strip("[]")
    family = socket.AF_INET6 if ":" in normalized else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as candidate:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                candidate.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            candidate.bind((normalized, port))
        return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("[ERRO] A porta deve estar entre 1 e 65535.", file=sys.stderr)
        return 2

    host = args.host or ("0.0.0.0" if args.lan else os.getenv("LEITURA_HOST", "127.0.0.1"))
    if not args.lan and not _is_loopback_host(host):
        print("[ERRO] Exposição à rede exige a opção explícita --lan.", file=sys.stderr)
        return 2

    certfile = None if args.no_https else _configured_path(args.certfile, "LEITURA_SSL_CERTFILE", DEFAULT_CERT)
    keyfile = None if args.no_https else _configured_path(args.keyfile, "LEITURA_SSL_KEYFILE", DEFAULT_KEY)
    try:
        certfile, keyfile = _validate_certificate_pair(certfile, keyfile)
    except ValueError as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 2

    https_enabled = certfile is not None
    os.environ["LEITURA_HTTPS"] = "1" if https_enabled else "0"
    os.environ["LEITURA_LAN_ENABLED"] = "1" if args.lan else "0"
    scheme = "https" if https_enabled else "http"

    existing = _find_existing_server(host, args.port, https_enabled)
    if existing is not None:
        if existing.https_enabled == https_enabled and existing.lan_enabled == args.lan:
            print(f"Leitura Ligeira já está ativa: {existing.url}")
            print("Nenhuma segunda instância foi iniciada.")
            return 0
        print(f"[ERRO] A porta {args.port} já contém outra instância do Leitura Ligeira.", file=sys.stderr)
        print(
            f"Instância ativa: {existing.url} (LAN {'ativa' if existing.lan_enabled else 'desativada'}).",
            file=sys.stderr,
        )
        print("Encerre a instância anterior com Ctrl+C ou escolha outra porta com --port.", file=sys.stderr)
        return 2

    if not _port_is_available(host, args.port):
        print(f"[ERRO] A porta {args.port} já está em uso por outro programa.", file=sys.stderr)
        print(
            f"Encerre o programa que ocupa a porta ou tente novamente com --port {args.port + 1}.",
            file=sys.stderr,
        )
        return 2

    print(f"Leitura Ligeira: {scheme}://127.0.0.1:{args.port}")
    if args.lan:
        local_ip = _local_ip()
        print(f"Rede local: {scheme}://{local_ip or '<IP-DESTE-PC>'}:{args.port}")
    if not https_enabled:
        print("[AVISO] HTTP sem criptografia. Use --lan somente em uma rede doméstica confiável.")
    print("Para encerrar, pressione Ctrl+C.\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=args.port,
        proxy_headers=False,
        server_header=False,
        date_header=False,
        ssl_certfile=str(certfile) if certfile else None,
        ssl_keyfile=str(keyfile) if keyfile else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())