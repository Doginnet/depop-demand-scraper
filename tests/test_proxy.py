from pathlib import Path
import pytest

from depop.client import DepopClient
from depop.config import Config
from depop.proxy import ProxyRotator, normalize_proxy_url


def test_proxy_empty_returns_none():
    """Verify default behavior without proxies is direct (None)."""
    rotator = ProxyRotator()
    assert not rotator.is_enabled
    assert rotator.total_count == 0
    assert rotator.get_proxy() is None


def test_normalize_proxy_url():
    """Verify various proxy string formats are correctly parsed."""
    # Standard URL
    assert (
        normalize_proxy_url("http://user:pass@192.168.1.1:8080")
        == "http://user:pass@192.168.1.1:8080"
    )
    assert (
        normalize_proxy_url("socks5://192.168.1.1:1080")
        == "socks5://192.168.1.1:1080"
    )

    # host:port:user:pass
    assert (
        normalize_proxy_url("192.168.1.1:8080:myuser:mypass")
        == "http://myuser:mypass@192.168.1.1:8080"
    )

    # host:port
    assert normalize_proxy_url("192.168.1.1:8080") == "http://192.168.1.1:8080"

    # Empty or whitespace
    assert normalize_proxy_url("   ") == ""


def test_round_robin_rotation():
    """Verify round-robin rotates sequentially through all active proxies."""
    raw_proxies = [
        "10.0.0.1:8080",
        "10.0.0.2:8080",
        "10.0.0.3:8080",
    ]
    rotator = ProxyRotator(proxies=raw_proxies, strategy="round_robin")
    assert rotator.is_enabled
    assert rotator.total_count == 3

    sequence = [rotator.get_proxy() for _ in range(6)]
    expected = [
        "http://10.0.0.1:8080",
        "http://10.0.0.2:8080",
        "http://10.0.0.3:8080",
        "http://10.0.0.1:8080",
        "http://10.0.0.2:8080",
        "http://10.0.0.3:8080",
    ]
    assert sequence == expected


def test_random_rotation():
    """Verify random rotation picks from active proxies."""
    raw_proxies = ["10.0.0.1:8080", "10.0.0.2:8080"]
    rotator = ProxyRotator(proxies=raw_proxies, strategy="random")
    for _ in range(10):
        proxy = rotator.get_proxy()
        assert proxy in ["http://10.0.0.1:8080", "http://10.0.0.2:8080"]


def test_load_from_file(tmp_path):
    """Verify loading proxies from text file ignoring comments and blank lines."""
    file_content = """
    # Proxy test file
    http://user:pass@proxy1.com:8080

    proxy2.com:3128:testuser:testpass
    # Another comment
    proxy3.com:80
    """
    p_file = tmp_path / "proxies.txt"
    p_file.write_text(file_content, encoding="utf-8")

    rotator = ProxyRotator(file_path=p_file)
    assert rotator.total_count == 3
    assert "http://user:pass@proxy1.com:8080" in rotator._proxies
    assert "http://testuser:testpass@proxy2.com:3128" in rotator._proxies
    assert "http://proxy3.com:80" in rotator._proxies


def test_quarantine_on_failures():
    """Verify failing proxy is quarantined and reactivated if all fail."""
    proxies = ["10.0.0.1:8080", "10.0.0.2:8080"]
    rotator = ProxyRotator(
        proxies=proxies, strategy="round_robin", max_consecutive_failures=2
    )

    p1 = "http://10.0.0.1:8080"
    rotator.report_failure(p1)
    assert rotator.active_count == 2
    rotator.report_failure(p1)
    # Exceeded max failures (2)
    assert rotator.active_count == 1

    # Only second proxy is returned now
    assert rotator.get_proxy() == "http://10.0.0.2:8080"
    assert rotator.get_proxy() == "http://10.0.0.2:8080"


def test_client_integration():
    """Verify DepopClient configures proxy_rotator properly."""
    config_direct = Config()
    client_direct = DepopClient(config=config_direct)
    assert not client_direct.proxy_rotator.is_enabled
    kwargs, proxy = client_direct._get_proxy_kwargs()
    assert kwargs == {}
    assert proxy is None

    config_proxied = Config(proxies=["myproxy.com:8080"])
    client_proxied = DepopClient(config=config_proxied)
    assert client_proxied.proxy_rotator.is_enabled
    kwargs, proxy = client_proxied._get_proxy_kwargs()
    assert kwargs == {"proxy": "http://myproxy.com:8080"}
    assert proxy == "http://myproxy.com:8080"
