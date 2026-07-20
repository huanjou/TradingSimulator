from app.services.auth import InvalidCredentialsException, UserAlreadyExistsException
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


async def user_already_exists_exception_handler(
    request: Request, exc: UserAlreadyExistsException
):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


async def invalid_credentials_exception_handler(
    request: Request, exc: InvalidCredentialsException
):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


def setup_exception_handlers(app: FastAPI):
    app.add_exception_handler(
        UserAlreadyExistsException, user_already_exists_exception_handler
    )
    app.add_exception_handler(
        InvalidCredentialsException, invalid_credentials_exception_handler
    )
