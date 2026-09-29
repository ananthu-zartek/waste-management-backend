from rest_framework.permissions import AllowAny


class AllowAnyMixin:
    def get_permissions(self):
        return [AllowAny()]


class AllowAnyForListMixin:
    def get_permissions(self):
        if getattr(self, "action", None) == "list":
            return [AllowAny()]
        return super().get_permissions()


class AllowAnyForCreateMixin:
    def get_permissions(self):
        if getattr(self, "action", None) == "create":
            return [AllowAny()]
        return super().get_permissions()
