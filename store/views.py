import stripe
from django.db import transaction
from django.db.models import F, Min
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from config import settings
from store.models.orders import Order
from store.serializers import (
    AddressSerializer,
    BrandSerializer,
    CategorySerializer,
    CheckoutSerializer,
    CouponSerializer,
    OrderSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ReviewSerializer,
    WishlistSerializer, CartSerializer,
)

from .filters import ProductFilter
from .models import Address, Brand, Category, Coupon, Payment, Product, Review, Wishlist
from .models.cart import Cart, CartItem
from .permissions import (
    IsAdminOrReadOnly,
    IsOwnerOrAdmin,
    IsReviewAuthorOrAdmin,
)

stripe.api_key = settings.STRIPE_SECRET_KEY


@extend_schema(tags=["Categories"])
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (IsAdminOrReadOnly,)


@extend_schema(tags=["Brands"])
class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = (IsAdminOrReadOnly,)


@extend_schema(tags=["Products"])
class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = (
            Product.objects.annotate(price=Min("variants__price"))
            .select_related("brand", "category")
            .prefetch_related("variants", "images")
        )
        if self.request.user.is_staff:
            return qs

        return qs.filter(is_active=True)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Reviews"],
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Filter reviews by product ID",
                required=False,
                type=int,
            )
        ],
    ),
    create=extend_schema(tags=["Reviews"]),
    retrieve=extend_schema(tags=["Reviews"]),
    update=extend_schema(tags=["Reviews"]),
    partial_update=extend_schema(tags=["Reviews"]),
    destroy=extend_schema(tags=["Reviews"]),
)
class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        queryset = Review.objects.select_related("product", "user")
        product_id = self.request.query_params.get("product_id")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema(tags=["Addresses"])
class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Address.objects.none()

        if self.request.user.is_staff:
            return Address.objects.all()
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema_view(
    list=extend_schema(tags=["Orders"]),
    retrieve=extend_schema(tags=["Orders"]),
    update=extend_schema(tags=["Orders"]),
    partial_update=extend_schema(tags=["Orders"]),
    destroy=extend_schema(tags=["Orders"]),
)
class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()

        base_qs = (
            Order.objects.prefetch_related("items__variant")
            .select_related("user", "coupon")
            .order_by("-created_at")
        )
        if self.request.user.is_staff:
            return base_qs
        return base_qs.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "checkout":
            return CheckoutSerializer
        return OrderSerializer

    @extend_schema(
        tags=["Orders"],
        request=CheckoutSerializer,
        responses={201: OrderSerializer},
        description="Checkout order for authenticated users and guests",
    )
    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def checkout(self, request):
        serializer = CheckoutSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            OrderSerializer(order).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        tags=["Orders"],
        responses={
            200: {"type": "object", "properties": {"checkout_url": {"type": "string"}}},
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
            403: {"type": "object", "properties": {"detail": {"type": "string"}}},
            404: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        description="Create Stripe Checkout Session for order payment",
    )
    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def pay(self, request, pk=None):
        order = Order.objects.filter(pk=pk).first()
        if not order:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if order.user is not None:
            if request.user != order.user and not request.user.is_staff:
                return Response(
                    {"detail": "You do not have permission to perform this action."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            guest_email = request.data.get("email")
            if not guest_email or guest_email.lower() != order.contact_email.lower():
                return Response(
                    {"detail": "Contact email is not valid for this order."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        if order.status != Order.Status.PENDING:
            return Response(
                {"detail": "Order is not pending payment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_cents = int(order.total_price * 100)
        try:
            session = stripe.checkout.Session.create(
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount_cents,
                            "product_data": {
                                "name": f"Order #{order.id}",
                            },
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                metadata={"order_id": str(order.id)},
                success_url=f"{request.scheme}://{request.get_host()}/api/docs/?status=success",
                cancel_url=f"{request.scheme}://{request.get_host()}/api/docs/?status=cancel",
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Payment.objects.create(
            order=order,
            provider="stripe",
            transaction_id=session.id,
            amount=order.total_price,
            status="pending",
        )
        return Response({"checkout_url": session.url}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Order creation is not allowed. Use /checkout/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {"detail": "Delete permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


@extend_schema(
    tags=["Payments"],
    description="Handle Stripe webhooks",
    responses={200: None, 400: None},
)
class StripeWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            order_id = session.get("metadata", {}).get("order_id")
            order = Order.objects.filter(id=order_id).first()

            if order and order.status != Order.Status.PAID:
                with transaction.atomic():
                    order.status = Order.Status.PAID
                    order.save(update_fields=["status"])

                    if order.coupon:
                        order.coupon.times_used = F("times_used") + 1
                        order.coupon.save(update_fields=["times_used"])

                    for item in order.items.select_related("variant"):
                        item.variant.quantity = F("quantity") - item.quantity
                        item.variant.save(update_fields=["quantity"])

                    payment = Payment.objects.filter(transaction_id=session["id"]).first()
                    if payment:
                        payment.status = Payment.Status.PAID
                        payment.save(update_fields=["status"])

        return Response(status=status.HTTP_200_OK)


@extend_schema(tags=["Wishlist"])
class WishlistViewSet(viewsets.ModelViewSet):
    queryset = Wishlist.objects.all()
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Wishlist.objects.none()

        qs = (
            Wishlist.objects.filter(user=self.request.user)
            .select_related("user", "product")
        )

        if self.request.user.is_staff:
            return Wishlist.objects.select_related("user", "product")
        return qs


@extend_schema(tags=["Coupons"])
class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdminOrReadOnly]

    @extend_schema(tags=["Coupons"])
    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def validate(self, request):
        code = request.data.get("code")
        if not code:
            return Response(
                {"detail": "Coupon code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon = Coupon.objects.filter(code=code).first()

        if not coupon:
            return Response(
                {"detail": "Invalid coupon code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not coupon.is_valid():
            return Response(
                {"detail": "Coupon is expired or inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "code": coupon.code,
            "discount_percentage": coupon.discount_percentage,
        })


class CartViewSet(viewsets.GenericViewSet):
    def get_cart(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

    def list(self, request):
        cart = self.get_cart()
        serializer = CartSerializer(cart, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def add(self, request):
        cart = self.get_cart()
        serializer = CartSerializer(cart, data=request.data)
        serializer.is_valid(raise_exception=True)

        variant = serializer.validated_data["variant"]
        quantity = serializer.validated_data["quantity"]

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, variant=variant, defaults={"quantity": quantity}
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            if variant.quantity < new_quantity:
                return Response(
                    {"detail": f"Only {variant.quantity} {variant.product.name} available in stock."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cart_item.quantity = new_quantity
            cart_item.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path="items/(?P<item_id>[^/.]+)")
    def remove_item(self, request, item_id=None):
        cart = self.get_cart()
        try:
            item = cart.items.get(id=item_id)
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CartItem.DoesNotExist:
            return Response(
                {"detail": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["post"])
    def clear(self, request):
        cart = self.get_cart()
        cart.items.all().delete()
        return Response({"detail": "Cart cleared."}, status=status.HTTP_200_OK)

