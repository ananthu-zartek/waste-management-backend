from django.db import models
from django.core.exceptions import ValidationError
from catalog.services import validate_service_pincode

from users.models import TimeStampedModel


class Booking(TimeStampedModel):
    class BookingType(models.TextChoices):
        WASTE = "waste", "Waste"
        SCRAP = "scrap", "Scrap"

    class BookingSource(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        ADMIN = "admin", "Admin"

    class BookingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ASSIGNED = "assigned", "Assigned"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    customer = models.ForeignKey(
        "customers.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    driver = models.ForeignKey(
        "drivers.DriverProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )
    address = models.ForeignKey(
        "customers.Address",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    slot = models.ForeignKey(
        "catalog.TimeSlot",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    scheduled_date = models.DateField()
    booking_type = models.CharField(
        max_length=20,
        choices=BookingType.choices,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=BookingSource.choices,
        default=BookingSource.CUSTOMER,
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        db_index=True,
    )
    estimated_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    other_notes = models.TextField(blank=True)
    estimated_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=["scheduled_date", "status"]),
            models.Index(fields=["source", "status", "created_at"]),
        ]

    def __str__(self):
        return f"Booking {self.pk} - {self.customer} - {self.scheduled_date}"

    def clean(self):
        super().clean()
        if self.address_id:
            if self.address.customer_id != self.customer_id:
                raise ValidationError(
                    {"address": "The address must belong to the customer."}
                )
            if self.pk:
                previous = (
                    type(self)
                    .objects.filter(pk=self.pk)
                    .values("address_id", "driver_id", "slot_id", "scheduled_date")
                    .first()
                )
                if previous and all(
                    getattr(self, field) == value for field, value in previous.items()
                ):
                    return
            if self.address.pincode_id is None:
                raise ValidationError(
                    {"address": "Select a supported pincode for this address."}
                )
            try:
                validate_service_pincode(self.address.pincode.pincode, self.driver)
            except ValidationError as exc:
                errors = dict(exc.message_dict)
                if "pincode" in errors:
                    errors["address"] = errors.pop("pincode")
                raise ValidationError(errors) from exc


class BookingRequest(TimeStampedModel):
    customer = models.ForeignKey("customers.CustomerProfile", on_delete=models.CASCADE)
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="creation_request",
        null=True,
        blank=True,
    )
    key = models.CharField(max_length=128)
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "key"], name="unique_booking_request"
            )
        ]


class BookingWasteItem(TimeStampedModel):
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="waste_items"
    )
    subcategory = models.ForeignKey(
        "catalog.WasteSubCategory",
        on_delete=models.PROTECT,
        related_name="booking_items",
    )
    estimated_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    def __str__(self):
        return f"Booking {self.booking_id} - {self.subcategory}"


class ScrapBooking(TimeStampedModel):
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name="scrap_booking"
    )

    def __str__(self):
        return f"Scrap booking {self.booking_id}"


class ScrapBookingItem(TimeStampedModel):
    name = models.CharField(max_length=150, blank=True, default="")
    material = models.ForeignKey(
        "catalog.ScrapMaterial", on_delete=models.PROTECT, related_name="booking_items"
    )
    scrap_booking = models.ForeignKey(
        ScrapBooking, on_delete=models.CASCADE, related_name="items"
    )
    estimated_payout = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    estimated_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
