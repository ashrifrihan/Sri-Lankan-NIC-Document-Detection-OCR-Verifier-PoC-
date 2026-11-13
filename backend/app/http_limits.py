from http import HTTPStatus

from starlette.responses import JSONResponse

from .config import settings


def api_error(status, detail, headers=None):
    try:
        code = HTTPStatus(status).name.lower()
    except ValueError:
        code = "http_error"
    return JSONResponse(
        {"code": code, "detail": detail},
        status_code=status, headers=headers,
    )


class UploadBodyLimit:
    """Bound multipart bodies before Starlette parses them into memory."""

    paths = {"/api/verify", "/api/v1/bookingpartner/verify"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"].rstrip("/") not in self.paths:
            await self.app(scope, receive, send)
            return

        limit = settings.MAX_REQUEST_BODY_BYTES
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None:
            if not length.isdigit() or len(length) > 20:
                await api_error(400, "Invalid Content-Length.")(scope, receive, send)
                return
            if int(length) > limit:
                await api_error(413, "Upload is too large.")(scope, receive, send)
                return

        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            total += len(message.get("body", b""))
            if total > limit:
                await api_error(413, "Upload is too large.")(scope, receive, send)
                return
            if message.get("body") or not message.get("more_body"):
                chunks.append(message)
            if not message.get("more_body"):
                break

        buffered = iter(chunks)

        async def replay():
            message = next(buffered, None)
            return message if message is not None else await receive()

        await self.app(scope, replay, send)
