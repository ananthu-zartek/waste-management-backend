from django.db.models.signals import post_save
from django.dispatch import receiver

from drivers.models import DriverSlot
from .models import Booking


@receiver(post_save, sender=Booking)
def delete_driver_slot_on_booking_cancelled(sender, instance, created, **kwargs):
    if instance.status == Booking.BookingStatus.CANCELLED:
        DriverSlot.objects.filter(booking=instance).delete()

