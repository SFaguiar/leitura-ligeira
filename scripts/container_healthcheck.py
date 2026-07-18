"""Container-local application health probe supporting optional HTTPS."""

import json
import ssl
import urllib.error
import urllib.request


def _healthy(url: str) -> bool:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context),
    )
    request = urllib.request.Request(
        f"{url}/system/health",
        headers={"User-Agent": "Leitura-Ligeira-Container-Health/1.0"},
    )
    try:
        with opener.open(request, timeout=2.0) as response:
            payload = json.loads(response.read(4096).decode("utf-8"))
            return response.status == 200 and payload.get("status") == "healthy"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def main() -> int:
    for scheme in ("https", "http"):
        if _healthy(f"{scheme}://127.0.0.1:8000"):
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())