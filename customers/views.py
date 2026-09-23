from rest_framework import viewsets

from .models import Address
from .serializers import AddressSerializer


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(customer__user=self.request.user).select_related(
            "customer__user"
        )

    def perform_create(self, serializer):
        customer_profile = self.request.user.customer_profile
        serializer.save(customer=customer_profile)
