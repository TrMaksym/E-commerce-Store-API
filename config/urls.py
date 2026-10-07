from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from store.views import ProductViewSet, CategoryViewSet, BrandViewSet, OrderViewSet, AddressViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'brands', BrandViewSet, basename='brands')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'addresses', AddressViewSet, basename='addresses')
# router.register(r'wishlist', WishlistViewSet, basename='wishlist')
# router.register(r'reviews', ReviewViewSet, basename='reviews')

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/auth/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path("api/auth/", include("users.urls")),
    path("api/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )