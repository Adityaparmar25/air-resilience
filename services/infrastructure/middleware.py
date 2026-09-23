"""Infrastructure Middleware & Production Exception Handlers.

Provides:
- CorrelationIdMiddleware: ensures every request has an X-Correlation-ID
- Safe exception handling: prevents stack trace and secret leakage to clients
"""

from datetime import datetime, timezone
import uuid
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from services.observability.logging import log_event


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware attaching an X-Correlation-ID to every request and response."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or f"corr_{uuid.uuid4().hex[:12]}"
        request.state.correlation_id = correlation_id

        # Log request receipt
        log_event(
            level="INFO",
            event="http_request_received",
            correlation_id=correlation_id,
            component="http_inbound",
            details={
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


def register_safe_exception_handlers(app: FastAPI) -> None:
    """Register safe production exception handlers on the FastAPI app."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        correlation_id = getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")

        # Log detailed error internally
        log_event(
            level="ERROR",
            event="unhandled_server_exception",
            correlation_id=correlation_id,
            component="error_handler",
            details={
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            },
        )

        # Return safe sanitized message to public user - zero stack trace leakage
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected server error occurred. The incident has been recorded.",
                "correlation_id": correlation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            headers={"X-Correlation-ID": correlation_id},
        )
