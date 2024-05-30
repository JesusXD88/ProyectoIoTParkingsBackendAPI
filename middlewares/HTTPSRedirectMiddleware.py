from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.scheme != "https":
            url = request.url.replace(scheme="https")
            return RedirectResponse(url)
        response = await call_next(request)
        return response
