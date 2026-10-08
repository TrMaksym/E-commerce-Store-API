import stripe
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
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
    OrderSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ReviewSerializer,
    WishlistSerializer,
)

from .models import Address, Brand, Category, Payment, Product, Review, Wishlist
from .permissions import (
    IsAdminOrReadOnly,
    IsOwnerOrAdmin,
    IsReviewAuthorOrAdmin,
)


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

    def get_queryset(self):
        if self.request.user.is_staff:
            return Product.objects.all().prefetch_related("variants", "images")
        return (
            Product.objects.filter(is_active=True)
            .prefetch_related("variants", "images")
            .select_related("category", "brand")
        )

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
                success_url=f"{request.build_absolute_uri()}/success/",
                cancel_url=f"{request.build_absolute_uri()}/cancel/",
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
            if order:
                order.status = Order.Status.PAID
                order.save()

            payment = Payment.objects.filter(transaction_id=session["id"]).first()
            if payment:
                payment.status = Payment.Status.PAID
                payment.save()

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