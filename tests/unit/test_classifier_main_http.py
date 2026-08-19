from aiohttp.test_utils import TestClient, TestServer

from classifier.main import build_http_app


class FakeService:
    def __init__(self, ready: bool) -> None:
        self._ready = ready

    def is_ready(self) -> bool:
        return self._ready


async def test_health_always_returns_ok():
    app = build_http_app(FakeService(ready=False))
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
        assert await resp.text() == "ok"


async def test_ready_returns_200_when_service_is_ready():
    app = build_http_app(FakeService(ready=True))
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/ready")
        assert resp.status == 200


async def test_ready_returns_503_when_service_is_not_ready():
    app = build_http_app(FakeService(ready=False))
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/ready")
        assert resp.status == 503


async def test_metrics_returns_prometheus_text_format():
    app = build_http_app(FakeService(ready=True))
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/metrics")
        assert resp.status == 200
        body = await resp.text()
        assert "classifier_verdicts_total" in body
