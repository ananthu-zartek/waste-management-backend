from users.models import User


class UserScopedQuerysetMixin:
    customer_lookup = None
    driver_lookup = None

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.user_type == User.UserType.ADMIN:
            return queryset
        if user.user_type == User.UserType.CUSTOMER and self.customer_lookup:
            return queryset.filter(**{self.customer_lookup: user})
        if user.user_type == User.UserType.DRIVER and self.driver_lookup:
            return queryset.filter(**{self.driver_lookup: user})
        return queryset.none()
