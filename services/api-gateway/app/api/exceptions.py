from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class OrderNotFoundException(Exception):
    pass


class OrderQueryServiceUnavailableException(Exception):
    pass


class UnauthorizedOrderAccessException(Exception):
    pass


class OrderSubmissionFailedException(Exception):
    pass


class OrderValidationException(Exception):
    pass


async def order_not_found_handler(request: Request, exc: OrderNotFoundException):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc) or "Order not found"},
    )


async def query_service_unavailable_handler(
    request: Request, exc: OrderQueryServiceUnavailableException
):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc) or "Query service unavailable"},
    )


async def unauthorized_access_handler(
    request: Request, exc: UnauthorizedOrderAccessException
):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc) or "Not authorized"},
    )


async def order_submission_failed_handler(
    request: Request, exc: OrderSubmissionFailedException
):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Failed to submit order"},
    )


async def order_validation_handler(request: Request, exc: OrderValidationException):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc) or "Validation failed"},
    )


def setup_exception_handlers(app: FastAPI):
    app.add_exception_handler(OrderNotFoundException, order_not_found_handler)
    app.add_exception_handler(
        OrderQueryServiceUnavailableException, query_service_unavailable_handler
    )
    app.add_exception_handler(
        UnauthorizedOrderAccessException, unauthorized_access_handler
    )
    app.add_exception_handler(
        OrderSubmissionFailedException, order_submission_failed_handler
    )
    app.add_exception_handler(OrderValidationException, order_validation_handler)
