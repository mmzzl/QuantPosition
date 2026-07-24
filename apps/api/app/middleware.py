import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        response: Response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")
