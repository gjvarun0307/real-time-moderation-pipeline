import asyncio

import structlog
import uvloop
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from common.config import IngestSettings
from ingest.service import IngestService, build_service

logger = structlog.get_logger()


def build_http_app(service: IngestService) -> web.Application:
    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def ready(_request: web.Request) -> web.Response:
        if service.is_ready():
            return web.Response(text="ready")
        return web.Response(text="not ready", status=503)

    async def metrics(_request: web.Request) -> web.Response:
        # set the header directly — aiohttp's content_type= param rejects
        # a charset embedded in the string, which prometheus's constant has
        return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/ready", ready)
    app.router.add_get("/metrics", metrics)
    return app


async def run(settings: IngestSettings, http_port: int = 8000) -> None:
    service = build_service(settings)
    await service.start()

    app = build_http_app(service)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", http_port)
    await site.start()
    logger.info("ingest_service_started", http_port=http_port)

    try:
        await asyncio.gather(service.run_ingest_loop(), service.run_produce_loop())
    finally:
        await service.stop()
        await runner.cleanup()


def main() -> None:
    uvloop.install()
    # required fields with no default (author_hash_salt) come from env
    # at runtime; mypy can't see that, hence the ignore here specifically
    asyncio.run(run(IngestSettings()))  # type: ignore[call-arg]


if __name__ == "__main__":
    main()
