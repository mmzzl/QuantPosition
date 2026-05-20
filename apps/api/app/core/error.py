from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
import logging



def _make_json_safe(error_dict: dict) -> dict:
    """Convert error dict to JSON-safe format by removing non-serializable objects."""
    result = {}
    for key, value in error_dict.items():
        if isinstance(value, dict):
            result[key] = _make_json_safe(value)
        elif isinstance(value, (str, int, float, bool, list, type(None))):
            result[key] = value
        elif hasattr(value, "__dict__"):
            result[key] = str(value)
        else:
            result[key] = str(value)
    return result


async def http_exception_handler(request: Request, exc: Exception):
    """HTTP异常处理 - 只处理非HTTPException的其他异常"""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    logging.error(f"HTTP异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误"},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理"""
    logging.error(f"请求验证异常: {exc}")
    errors = exc.errors()
    safe_errors = [_make_json_safe(error) for error in errors]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": safe_errors},
    )


def setup_error_handlers(app):
    """设置错误处理"""
    app.add_exception_handler(Exception, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
