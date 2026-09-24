from rest_framework import viewsets
from catalog.views import CatalogPermission

from .models import DriverProfile
from .serializers import DriverProfileSerializer


class DriverProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [CatalogPermission]
    queryset = DriverProfile.objects.select_related("user").prefetch_related("service_pincodes")
    serializer_class = DriverProfileSerializer
