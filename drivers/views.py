from rest_framework import viewsets

from .models import DriverProfile
from .serializers import DriverProfileSerializer


class DriverProfileViewSet(viewsets.ModelViewSet):
    queryset = DriverProfile.objects.select_related("user")
    serializer_class = DriverProfileSerializer
