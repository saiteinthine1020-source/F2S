"""Exact-origin and strict JSON checks for browser authentication mutations."""

from dataclasses import dataclass

from fastapi import Request


class BrowserSecurityDenied(Exception):
    def __init__(self, *, status_code: int, code: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BrowserRequest:
    origin: str


async def require_browser_request(request: Request) -> BrowserRequest:
    origin = request.headers.get("Origin")
    if origin != request.app.state.settings.frontend_origin:
        raise BrowserSecurityDenied(status_code=403, code="ORIGIN_DENIED")
    assert origin is not None
    media_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise BrowserSecurityDenied(status_code=415, code="UNSUPPORTED_MEDIA_TYPE")
    return BrowserRequest(origin=origin)
