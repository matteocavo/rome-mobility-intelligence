"""Public quotas distinguish verified clients while bounding all limiter state."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.http_security import RateBudgets
from app.main import create_app


def config(**kwargs):
    return Settings(_env_file=None, environment="test", **kwargs)


def scope(ip, headers=()):
    return {"client": (ip, 12345), "headers": list(headers)}


def test_independent_clients_have_separate_quotas_and_denied_abuse_cannot_use_global():
    rates = RateBudgets(config(rate_limit_public=2, rate_limit_public_global=5))
    a = rates.client_identity(scope("198.51.100.1"))
    b = rates.client_identity(scope("198.51.100.2"))
    assert a != b and len(a) == 16
    assert rates.admit("public", a) == rates.admit("public", a) == 0
    for _ in range(100):
        assert rates.admit("public", a) > 0
    assert len(rates.buckets["public"]) == 2
    assert rates.admit("public", b) == rates.admit("public", b) == 0


def test_global_safety_ceiling_covers_multiple_clients():
    rates = RateBudgets(config(rate_limit_public=10, rate_limit_public_global=3))
    for index in range(3):
        assert rates.admit("public", str(index).encode()) == 0
    assert rates.admit("public", b"fourth") > 0
    assert len(rates.buckets["public"]) == 3
    assert b"fourth" not in rates.clients


def test_client_cardinality_is_bounded_and_active_quota_is_never_evicted():
    clock = [0.0]
    rates = RateBudgets(
        config(rate_limit_public=1, public_max_client_buckets=2), clock=lambda: clock[0]
    )
    assert rates.admit("public", b"a") == rates.admit("public", b"b") == 0
    for index in range(10000):
        assert rates.admit("public", str(index).encode()) > 0
    assert len(rates.clients) == 2
    assert rates.admit("public", b"a") > 0
    clock[0] = 60
    assert rates.admit("public", b"c") == 0
    assert len(rates.clients) <= 2
    assert rates.admit("public", b"a") == 0


def test_untrusted_headers_cannot_rotate_identity():
    rates = RateBudgets(config())
    one = rates.client_identity(scope("198.51.100.1"))
    for supplied in [b"8.8.8.8", b"1.1.1.1", b"10.0.0.1", b"bad"]:
        assert (
            rates.client_identity(
                scope(
                    "198.51.100.1",
                    [
                        (b"x-forwarded-for", supplied),
                        (b"cf-connecting-ip", supplied),
                        (b"forwarded", supplied),
                    ],
                )
            )
            == one
        )


def test_trusted_render_proxy_uses_single_validated_cf_address_not_spoofed_xff():
    rates = RateBudgets(
        config(
            public_client_ip_header="cf-connecting-ip",
            public_trusted_proxy_cidrs=["10.1.2.0/24"],
            rate_limit_public=1,
        )
    )

    def edge(value):
        return rates.client_identity(
            scope(
                "10.1.2.3", [(b"cf-connecting-ip", value), (b"x-forwarded-for", b"FAKE, 9.9.9.9")]
            )
        )

    assert edge(b"8.8.8.8") != edge(b"1.1.1.1")
    assert rates.admit("public", edge(b"8.8.8.8")) == 0
    assert rates.admit("public", edge(b"8.8.8.8")) > 0
    assert rates.admit("public", edge(b"1.1.1.1")) == 0
    for value in [b"bad", b"8.8.8.8, 1.1.1.1", b"127.0.0.1", b"10.1.2.3"]:
        assert edge(value) is None
    assert rates.client_identity(scope("10.1.2.3")) is None
    assert rates.client_identity(scope("10.1.2.3", [(b"cf-connecting-ip", b"8.8.8.8")] * 2)) is None
    assert rates.client_identity(
        scope("198.51.100.1", [(b"cf-connecting-ip", b"8.8.8.8")])
    ) == rates.client_identity(scope("198.51.100.1"))


def test_ipv6_privacy_addresses_share_a_subnet_budget():
    rates = RateBudgets(config())
    assert rates.client_identity(scope("2001:db8:1234:5678::1")) == rates.client_identity(
        scope("2001:db8:1234:5678::2")
    )


@pytest.mark.parametrize(
    "values",
    [
        dict(public_client_ip_header="cf-connecting-ip"),
        dict(public_trusted_proxy_cidrs=["10.1.2.0/24"]),
        dict(public_client_ip_header="cf-connecting-ip", public_trusted_proxy_cidrs=["0.0.0.0/0"]),
    ],
)
def test_proxy_trust_cannot_be_implicit_or_wildcard(values):
    with pytest.raises(RuntimeError, match="Deployment configuration"):
        create_app(config(**values))


def test_http_clients_isolated_and_abuse_gets_429_with_safe_retry():
    app = create_app(config(rate_limit_public=1))
    with TestClient(app, client=("198.51.100.1", 12345)) as first:
        assert first.get("/public/routes").status_code == 200
        denied = first.get("/public/routes", headers={"X-Forwarded-For": "8.8.8.8"})
        assert denied.status_code == 429 and denied.headers["retry-after"]
        # Second socket peer uses the same ASGI app/limiter, not a fresh app budget.
        with TestClient(app, client=("198.51.100.2", 12346)) as second:
            assert second.get("/public/routes").status_code == 200
