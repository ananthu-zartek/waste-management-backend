from users.models import User
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import CustomerProfile


class CustomerProfileRequiredMixin:
    def get_customer_profile(self):
        user = self.context["request"].user
        if user.user_type != User.UserType.CUSTOMER:
            raise PermissionDenied("Only customers can perform this action.")
        customer = CustomerProfile.objects.filter(user=user).first()
        if customer is None:
            raise NotFound("Customer profile not found.")
        return customer


class UserScopedQuerysetMixin:
    user_lookup = "user"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.user_type == User.UserType.ADMIN:
            return queryset
        return queryset.filter(**{self.user_lookup: self.request.user})
