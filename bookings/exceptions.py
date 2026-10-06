from django.core.exceptions import ValidationError


class NoSlotAvailable(ValidationError):
    def __init__(self):
        super().__init__("No slots available.")


class NoDriversAvailable(ValidationError):
    def __init__(self):
        super().__init__("Sorry ! No drivers available at the moment.")
