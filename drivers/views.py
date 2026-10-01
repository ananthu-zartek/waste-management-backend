from rest_framework import viewsets
from customers.mixins import UserScopedQuerysetMixin

from .models import DriverProfile
from .serializers import DriverProfileSerializer


class DriverProfileViewSet(UserScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DriverProfile.objects.select_related("user").prefetch_related(
        "service_pincodes"
    )
    serializer_class = DriverProfileSerializer
