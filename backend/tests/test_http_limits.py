import asyncio
import io

import httpx
from PIL import Image
from pydantic import SecretStr

from app.config import settings
from app.main import app, health_check, ocr_service


def test_declared_and_streamed_oversized_bodies_return_json(monkeypatch):
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 12)

    async def chunks():
        yield b"x" * 8
        yield b"x" * 8

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for body in (b"x" * 16, chunks()):
                response = await client.post("/api/verify", content=body)
                assert response.status_code == 413
                assert response.json() == {"code": "request_entity_too_large", "detail": "Upload is too large."}

    asyncio.run(exercise())


def test_booking_auth_and_rate_limit_run_before_body_read(monkeypatch):
    key = "A" * 64
    monkeypatch.setattr(settings, "BOOKINGPARTNER_API_KEY", SecretStr(key))
    monkeypatch.setattr(settings, "BOOKINGPARTNER_REQUESTS_PER_MINUTE", 0)

    async def unread_body():
        raise AssertionError("Request body must not be read")
        yield b""

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            path = "/api/v1/bookingpartner/verify"
            denied = await client.post(path, content=unread_body())
            assert denied.status_code == 401
            assert denied.json()["code"] == "unauthorized"
            throttled = await client.post(path, content=unread_body(), headers={"X-API-Key": key})
            assert throttled.status_code == 429
            assert throttled.headers["Retry-After"] == "60"

    asyncio.run(exercise())


def test_validation_errors_do_not_echo_input():
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/validate-nic", json={"nic_number": ["private input"]})
            assert response.status_code == 422
            assert response.json()["detail"] == "Request fields are missing or invalid."
            assert "private input" not in response.text

    asyncio.run(exercise())


def test_readiness_reports_unavailable_after_failed_warmup(monkeypatch):
    monkeypatch.setattr(settings, "OCR_WARMUP", True)
    monkeypatch.setattr(ocr_service, "active_engine", None)
    response = health_check()
    assert response.status_code == 503
    assert b'"models_loaded"' in response.body


def test_valid_multipart_reaches_verifier(monkeypatch):
    monkeypatch.setattr(ocr_service, "run_ocr", lambda *args, **kwargs: (["853451234V"], .9, {}))
    image = io.BytesIO()
    Image.new("RGB", (600, 400), color="white").save(image, format="PNG")

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/verify", files={"front_image": ("front.png", image.getvalue(), "image/png")})
            assert response.status_code == 200
            assert response.json()["extracted_nic"] == "853451234V"

    asyncio.run(exercise())
