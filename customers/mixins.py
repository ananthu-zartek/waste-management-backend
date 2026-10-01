from users.models import User


class UserScopedQuerysetMixin:
    user_lookup = "user"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.user_type == User.UserType.ADMIN:
            return queryset
        return queryset.filter(**{self.user_lookup: self.request.user})
