import os
from dataclasses import dataclass
from typing import Mapping


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})
APP_VERSION = "1.0.0-dev"


def _read_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise RuntimeError(
        f"{name} deve usar 1/0, true/false, yes/no ou on/off; recebido: {raw!r}."
    )


@dataclass(frozen=True)
class TransportSecurityConfig:
    https_enabled: bool = False
    lan_enabled: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "TransportSecurityConfig":
        source = os.environ if env is None else env
        return cls(
            https_enabled=_read_bool(source, "LEITURA_HTTPS"),
            lan_enabled=_read_bool(source, "LEITURA_LAN_ENABLED"),
        )
