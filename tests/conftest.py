import urllib.request

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network call in test")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
