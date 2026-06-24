"""WooCommerce credential env parsing."""

from __future__ import annotations

import store_credentials


def test_wc_consumer_key_secret_pair(monkeypatch):
    for key in list(__import__("os").environ):
        if key.startswith("STORE_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("STORE_NUNAORGANICA_PE_WC_CONSUMER_KEY", "ck_test")
    store_credentials.reload_credentials()

    monkeypatch.setenv("STORE_NUNAORGANICA_PE_WC_CONSUMER_SECRET", "cs_test")
    store_credentials.reload_credentials()
    cfg = store_credentials.resolve_store_config("nunaorganica_pe")
    assert cfg["wc_consumer_key"] == "ck_test"
    assert cfg["wc_consumer_secret"] == "cs_test"
    assert store_credentials.has_store_credentials("nunaorganica_pe")


def test_woocommerce_public_store_without_keys():
    assert store_credentials.has_store_credentials("nunaorganica_pe")
