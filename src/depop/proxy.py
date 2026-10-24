from dataclasses import dataclass, field
from itertools import cycle
from pathlib import Path
import random
import re
from typing import Literal
from loguru import logger


def normalize_proxy_url(proxy_str: str) -> str:
    """Normalize various proxy formats into standard URL format.

    Supported formats:
    - http://user:pass@host:port -> keep as is
    - socks5://user:pass@host:port -> keep as is
    - host:port:user:pass -> http://user:pass@host:port
    - host:port -> http://host:port
    """
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return ""

    # Already has protocol scheme
    if proxy_str.startswith(("http://", "https://", "socks5://", "socks5h://")):
        return proxy_str

    # Pattern: host:port:user:pass
    parts = proxy_str.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"

    # Pattern: host:port
    if len(parts) == 2:
        host, port = parts
        return f"http://{host}:{port}"

    # Default fallback: prepend http://
    return f"http://{proxy_str}"


@dataclass
class ProxyStats:
    successes: int = 0
    failures: int = 0
    is_active: bool = True


class ProxyRotator:
    """Thread-safe proxy rotator supporting round-robin and random rotation,

    with automatic format normalization and error tracking.
    If no proxies are provided, behaves as a passthrough (returns None).
    """

    def __init__(
        self,
        proxies: list[str] | None = None,
        file_path: str | Path | None = None,
        strategy: Literal["round_robin", "random"] = "round_robin",
        max_consecutive_failures: int = 3,
    ):
        self.strategy = strategy
        self.max_consecutive_failures = max_consecutive_failures
        self._proxies: list[str] = []
        self._stats: dict[str, ProxyStats] = {}
        self._iterator = None

        if proxies:
            self.add_proxies(proxies)

        if file_path:
            self.load_from_file(file_path)

    def add_proxies(self, proxies: list[str]) -> None:
        """Add and normalize a list of proxy strings."""
        for p in proxies:
            norm = normalize_proxy_url(p)
            if norm and norm not in self._stats:
                self._proxies.append(norm)
                self._stats[norm] = ProxyStats()

        self._reset_iterator()

    def load_from_file(self, file_path: str | Path) -> int:
        """Load proxies from a plain text file (one proxy per line)."""
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Proxies file '{path}' not found.")
            return 0

        loaded = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            valid = []
            for line in lines:
                clean = line.strip()
                if clean and not clean.startswith("#"):
                    valid.append(clean)
            self.add_proxies(valid)
            loaded = len(valid)
            logger.info(f"Loaded {loaded} proxies from '{path}'.")
        except Exception as e:
            logger.error(f"Failed to read proxies from '{path}': {e}")

        return loaded

    def _reset_iterator(self):
        active = [p for p in self._proxies if self._stats[p].is_active]
        self._iterator = cycle(active) if active else None

    def get_proxy(self) -> str | None:
        """Retrieve the next active proxy according to the configured strategy.

        Returns None if no active proxies are available (direct connection).
        """
        if not self._proxies:
            return None

        active = [p for p in self._proxies if self._stats[p].is_active]
        if not active:
            logger.warning("All proxies are quarantined; resetting active status.")
            for stats in self._stats.values():
                stats.is_active = True
                stats.failures = 0
            active = list(self._proxies)
            self._reset_iterator()

        if self.strategy == "random":
            return random.choice(active)

        # Round-robin default
        if self._iterator is None:
            self._reset_iterator()

        try:
            return next(self._iterator)
        except (StopIteration, TypeError):
            self._reset_iterator()
            return next(self._iterator) if self._iterator else None

    def report_success(self, proxy: str | None) -> None:
        """Record successful request through proxy."""
        if not proxy or proxy not in self._stats:
            return
        stats = self._stats[proxy]
        stats.successes += 1
        stats.failures = 0

    def report_failure(self, proxy: str | None) -> None:
        """Record failed request and quarantine if threshold is exceeded."""
        if not proxy or proxy not in self._stats:
            return
        stats = self._stats[proxy]
        stats.failures += 1
        if stats.failures >= self.max_consecutive_failures:
            stats.is_active = False
            logger.warning(
                f"Proxy '{proxy}' quarantined after {stats.failures} consecutive failures."
            )
            self._reset_iterator()

    @property
    def is_enabled(self) -> bool:
        """Return True if rotator has any configured proxies."""
        return len(self._proxies) > 0

    @property
    def total_count(self) -> int:
        return len(self._proxies)

    @property
    def active_count(self) -> int:
        return sum(1 for p in self._proxies if self._stats[p].is_active)

    def __len__(self) -> int:
        return self.total_count
