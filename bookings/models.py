from django.db import models

from users.models import SystemConfiguration, TimeStampedModel
from django.utils import timezone


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
        db_index=False,
    )
    driver = models.ForeignKey(
        "drivers.DriverProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
        db_index=False,
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
        db_index=False,
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
    previous_driver = models.ForeignKey(
        "drivers.DriverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="previous_bookings",
    )
    reassigned_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_notes = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_bookings",
    )
    expired_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    estimated_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=["scheduled_date", "status"]),
            models.Index(fields=["source", "status", "created_at"]),
            models.Index(
                fields=["slot", "scheduled_date"], name="booking_slot_date_idx"
            ),
            models.Index(
                fields=["customer", "scheduled_date"], name="booking_customer_date_idx"
            ),
            models.Index(
                fields=["driver", "scheduled_date"], name="booking_driver_date_idx"
            ),
        ]

    @property
    def system_configuration(self):
        return SystemConfiguration.objects.first()

    def is_confirmation_expired(self):
        return (
            timezone.now()
            >= self.created_at + SystemConfiguration.get_confirmation_window()
        )

    def save(self, *args, **kwargs):
        now = timezone.now()

        if self.status == self.BookingStatus.CONFIRMED and self.confirmed_at is None:
            self.confirmed_at = timezone.now()

        if self.status == self.BookingStatus.CANCELLED and self.cancelled_at is None:
            self.cancelled_at = timezone.now()

        if self.driver_id and self.assigned_at is None:
            self.assigned_at = now

        if self.pk:
            old_booking = Booking.objects.get(pk=self.pk)
            if old_booking.driver_id != self.driver_id:
                self.previous_driver = old_booking.driver
                self.reassigned_at = now
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking {self.pk} - {self.customer} - {self.scheduled_date}"


class BookingWasteItem(TimeStampedModel):
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="waste_items"
    )
    subcategory = models.ForeignKey(
        "catalog.WasteSubCategory",
        on_delete=models.PROTECT,
        related_name="booking_items",
    )

    def __str__(self):
        return f"Booking {self.booking_id} - {self.subcategory}"


class ScrapBookingItem(TimeStampedModel):
    material = models.ForeignKey(
        "catalog.ScrapMaterial", on_delete=models.PROTECT, related_name="booking_items"
    )
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="scrap_items"
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
