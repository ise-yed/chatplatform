import logging
from collections.abc import Mapping

from django.conf import settings
from django.core.exceptions import (
    BadRequest as DjangoBadRequest,
)
from django.core.exceptions import (
    ObjectDoesNotExist,
    SuspiciousOperation,
)
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db import DatabaseError, IntegrityError
from django.db.models import ProtectedError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    ErrorDetail,
)
from rest_framework.exceptions import (
    NotFound as DRFNotFound,
)
from rest_framework.exceptions import (
    PermissionDenied as DRFPermissionDenied,
)
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def _stringify_error(value):
    if isinstance(value, ErrorDetail):
        return str(value)

    if isinstance(value, list):
        return [_stringify_error(item) for item in value]

    if isinstance(value, tuple):
        return [_stringify_error(item) for item in value]

    if isinstance(value, Mapping):
        return {key: _stringify_error(item) for key, item in value.items()}

    return value


def _extract_error_code(value, default="api_error"):
    if isinstance(value, ErrorDetail):
        return value.code or default

    if isinstance(value, list) and value:
        return _extract_error_code(value[0], default=default)

    if isinstance(value, tuple) and value:
        return _extract_error_code(value[0], default=default)

    if isinstance(value, Mapping):
        detail = value.get("detail")
        if detail is not None:
            return _extract_error_code(detail, default=default)

        for item in value.values():
            code = _extract_error_code(item, default=None)
            if code:
                return code

    return default


def _get_message_from_data(data, fallback):
    if isinstance(data, Mapping):
        detail = data.get("detail")
        if detail is not None:
            return str(detail)

        non_field_errors = data.get("non_field_errors")
        if isinstance(non_field_errors, list) and non_field_errors:
            return str(non_field_errors[0])

        return fallback

    if isinstance(data, list) and data:
        return str(data[0])

    return fallback


def _build_error_response(*, message, error_code, errors, status_code):
    payload = {
        "message": message,
        "error_code": error_code,
        "errors": errors,
    }

    if settings.DEBUG:
        payload["status_code"] = status_code

    return Response(payload, status=status_code)


def custom_exception_handler(exc, context):
    original_exc = exc

    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            detail = exc.message_dict
        elif hasattr(exc, "messages"):
            detail = exc.messages
        else:
            detail = [str(exc)]

        exc = DRFValidationError(detail=detail)

    elif isinstance(exc, DjangoPermissionDenied):
        exc = DRFPermissionDenied(detail=str(exc) or "Permission denied.")

    elif isinstance(exc, (Http404, ObjectDoesNotExist)):
        exc = DRFNotFound(detail="The requested object was not found.")

    elif isinstance(exc, DjangoBadRequest):
        api_exc = APIException(detail=str(exc) or "Bad request.")
        api_exc.status_code = status.HTTP_400_BAD_REQUEST
        api_exc.default_code = "bad_request"
        exc = api_exc

    elif isinstance(exc, SuspiciousOperation):
        logger.warning("Suspicious operation: %s", exc, exc_info=True)

        api_exc = APIException(detail="Invalid request.")
        api_exc.status_code = status.HTTP_400_BAD_REQUEST
        api_exc.default_code = "suspicious_operation"
        exc = api_exc

    elif isinstance(exc, ProtectedError):
        logger.info("Protected object error: %s", exc, exc_info=True)

        api_exc = APIException(detail="This object cannot be deleted because it is in use.")
        api_exc.status_code = status.HTTP_409_CONFLICT
        api_exc.default_code = "protected_object"
        exc = api_exc

    elif isinstance(exc, IntegrityError):
        logger.info("Database integrity error: %s", exc, exc_info=True)

        api_exc = APIException(detail="Database integrity error.")
        api_exc.status_code = status.HTTP_409_CONFLICT
        api_exc.default_code = "integrity_error"
        exc = api_exc

    elif isinstance(exc, DatabaseError):
        logger.error("Database error: %s", exc, exc_info=True)

        api_exc = APIException(detail="Database error.")
        api_exc.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        api_exc.default_code = "database_error"
        exc = api_exc

    response = drf_exception_handler(exc, context)

    if response is None:
        logger.error("Unhandled exception: %s", original_exc, exc_info=True)

        message = (
            f"Unhandled exception: {original_exc}" if settings.DEBUG else "A server error occurred."
        )

        return _build_error_response(
            message=message,
            error_code="unhandled_error" if settings.DEBUG else "server_error",
            errors=None,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    data = response.data
    normalized_errors = _stringify_error(data)

    if isinstance(exc, DRFValidationError):
        message = "Invalid input provided."
        error_code = "validation_error"
        errors = normalized_errors

    elif isinstance(exc, APIException):
        default_code = getattr(exc, "default_code", "api_error")
        message = _get_message_from_data(
            normalized_errors,
            fallback=getattr(exc, "default_detail", "An error occurred."),
        )
        error_code = _extract_error_code(data, default=default_code)
        errors = None

        if isinstance(normalized_errors, Mapping):
            if "detail" not in normalized_errors:
                errors = normalized_errors
        elif isinstance(normalized_errors, list):
            errors = {"non_field_errors": normalized_errors}

    else:
        message = "An error occurred."
        error_code = "generic_error"
        errors = normalized_errors

    response.data = {
        "message": str(message),
        "error_code": str(error_code),
        "errors": errors,
    }

    if settings.DEBUG:
        response.data["status_code"] = response.status_code

    return response
