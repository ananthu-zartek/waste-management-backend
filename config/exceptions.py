import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

logger = logging.getLogger(__name__)


def error_reason(detail):
    if isinstance(detail, dict):
        return "; ".join(error_reason(value) for value in detail.values())
    if isinstance(detail, (list, tuple)):
        return "; ".join(error_reason(value) for value in detail)
    return str(detail)


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(getattr(exc, "message_dict", exc.messages))
    elif isinstance(exc, ObjectDoesNotExist):
        exc = NotFound("The requested record does not exist.")

    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = {"error": error_reason(response.data)}
        return response

    set_rollback()
    if isinstance(exc, IntegrityError):
        return Response(
            {"error": "This operation conflicts with existing or related records."},
            status=409,
        )

    logger.error(
        "Unhandled API exception", exc_info=(type(exc), exc, exc.__traceback__)
    )
    return Response(
        {"error": "An unexpected error occurred. Please try again later."}, status=500
    )


def bad_request(request, exception):
    return JsonResponse({"error": "Invalid request."}, status=400)


def permission_denied(request, exception):
    return JsonResponse({"error": "Permission denied."}, status=403)


def not_found(request, exception):
    return JsonResponse({"error": "The requested resource was not found."}, status=404)


def server_error(request):
    return JsonResponse({"error": "An unexpected error occurred."}, status=500)
