from django.core.exceptions import ValidationError
from rest_framework.exceptions import APIException


class IdempotencyConflict(APIException):
    status_code = 409
    default_detail = "This Idempotency-Key was already used with a different payload."


class NoSlotAvailable(ValidationError):
    def __init__(self):
        super().__init__("No drivers available for this date and time slot.")
