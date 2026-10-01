from rest_framework import viewsets

from .models import Address, CustomerProfile
from .serializers import CustomerProfileSerializer, AddressSerializer
from .mixins import UserScopedQuerysetMixin


class CustomerProfileViewSet(UserScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = CustomerProfile.objects.select_related("user")
    serializer_class = CustomerProfileSerializer
    user_lookup = "user"


class AddressViewSet(UserScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Address.objects.select_related(
        "customer__user",
        "pincode",
    ).order_by("-is_default", "id")
    serializer_class = AddressSerializer
    user_lookup = "customer__user"

    def perform_create(self, serializer):
        customer_profile = self.request.user.customer_profile
        serializer.save(customer=customer_profile)
