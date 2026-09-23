from rest_framework.routers import DefaultRouter

from .views import UserViewSet

router = DefaultRouter()
router.register("auth", UserViewSet, basename="auth")

urlpatterns = router.urls
