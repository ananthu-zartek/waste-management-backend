from django.core.exceptions import ValidationError

from .models import ServicePincode


def validate_service_pincode(pincode, driver=None):
    supported = ServicePincode.objects.filter(
        pincode=pincode, is_active=True, service_area__is_active=True
    )
    if not supported.exists():
        raise ValidationError({"pincode": "Select an active service-area pincode."})
    if driver is not None and not supported.filter(drivers=driver).exists():
        raise ValidationError({"driver": "This driver does not serve the selected pincode."})
