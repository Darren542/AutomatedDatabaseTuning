from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def invalid_request_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    # Default validation details may echo bodies, credentials, or arbitrary keys.
    # Do not log error/body or return the submitted values or error locations.
    return JSONResponse(status_code=422, content={
        "detail": "Invalid request. Check required fields, field types, authentication mode, and timeout values (1–60 seconds)."
    })
