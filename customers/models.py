from django.db import models
from django.core.exceptions import ValidationError
from catalog.models import ServicePincode
from users.models import User


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    def __str__(self):
        return str(self.user.phone_number)


class Address(models.Model):
    class AddressType(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
    )
    house_no = models.CharField(max_length=100)
    area = models.CharField(max_length=150)
    city = models.CharField(max_length=100)
    pincode = models.ForeignKey(
        "catalog.ServicePincode",
        on_delete=models.SET_NULL,
        null=True,
        related_name="addresses",
        limit_choices_to={"is_active": True, "service_area__is_active": True},
    )

    def clean(self):
        super().clean()
        if not ServicePincode.objects.filter(
            pk=self.pincode_id, is_active=True, service_area__is_active=True
        ).exists():
            raise ValidationError({"pincode": "Select an active service-area pincode."})
        if self.pk:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("pincode_id", flat=True)
                .first()
            )
            if (
                previous != self.pincode_id
                and self.bookings.exclude(
                    status__in=["completed", "cancelled", "expired"]
                ).exists()
            ):
                raise ValidationError(
                    {
                        "pincode": "Cannot change the pincode while this address has active bookings."
                    }
                )

    def __str__(self):
        return f"{self.customer} - {self.address_type}"
