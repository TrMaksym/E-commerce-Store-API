from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from store.views import ProductViewSet, CategoryViewSet, BrandViewSet, OrderViewSet, AddressViewSet, WishlistViewSet, \
    ReviewViewSet, StripeWebhookView, CouponViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'brands', BrandViewSet, basename='brands')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'addresses', AddressViewSet, basename='addresses')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')
router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'coupons', CouponViewSet, basename='coupons')
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("rest_framework.urls")),
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
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    ]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )