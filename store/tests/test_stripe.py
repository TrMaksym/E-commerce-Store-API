import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from store.models import Category, Coupon, Order, OrderItem, Payment, Product, ProductVariant
from store.services.stripe_service import StripeService

User = get_user_model()


@pytest.fixture
def user():
    uid = uuid.uuid4().hex[:6]
    return User.objects.create_user(
        email=f"user_{uid}@example.com",
        password="password123",
    )


@pytest.fixture
def product():
    uid = uuid.uuid4().hex[:6]
    cat = Category.objects.create(name=f"Cat {uid}", slug=f"cat-{uid}")
    return Product.objects.create(category=cat, name=f"Shoes {uid}", slug=f"shoes-{uid}")


@pytest.fixture
def variant(product):
    uid = uuid.uuid4().hex[:6]
    return ProductVariant.objects.create(
        product=product,
        sku=f"SKU-{uid}",
        name="Size 43",
        price=Decimal("80.00"),
        quantity=5,
    )


@pytest.fixture
def order(user, variant):
    order = Order.objects.create(
        user=user,
        shipping_address="Address 1",
        contact_phone="+3901234567",
        contact_email=user.email,
        subtotal_price=Decimal("80.00"),
        total_price=Decimal("80.00"),
        status=Order.Status.PENDING,
    )
    order.items.product = product
    OrderItem.objects.create(
        order=order,
        variant=variant,
        price=variant.price,
        quantity=1,
    )
    return order


@pytest.mark.django_db
def test_stripe_service_create_checkout_session_empty_order(user):
    empty_order = Order.objects.create(
        user=user,
        shipping_address="Address",
        contact_phone="123",
        contact_email=user.email,
    )
    with pytest.raises(ValidationError):
        StripeService.create_checkout_session(empty_order, "http://success", "http://cancel")


@pytest.mark.django_db
def test_stripe_service_create_checkout_session_success(order):
    mock_session = MagicMock()
    mock_session.id = "cs_live_123"
    mock_session.url = "https://stripe.com/pay"

    with patch.object(order.items.first(), "product", create=True) as mock_prod:
        mock_prod.title = "Test Shoes"
        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
            with patch.object(OrderItem, "product", create=True, new_callable=lambda: property(lambda self: MagicMock(title="Test Shoes"))):
                session = StripeService.create_checkout_session(order, "http://success", "http://cancel")

                assert session == mock_session
                mock_create.assert_called_once()
                args, kwargs = mock_create.call_args
                assert kwargs["mode"] == "payment"
                assert kwargs["metadata"]["order_id"] == str(order.id)
                assert kwargs["line_items"][0]["quantity"] == 1
                assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 8000


def test_stripe_service_construct_webhook_event():
    with patch("stripe.Webhook.construct_event", return_value={"type": "test"}) as mock_construct:
        payload = b'{"type": "test"}'
        sig = "sig_header_123"
        event = StripeService.construct_webhook_event(payload, sig)
        assert event == {"type": "test"}
        mock_construct.assert_called_once_with(
            payload=payload,
            sig_header=sig,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )


@pytest.mark.django_db
def test_handle_checkout_completed_no_order_id():
    StripeService.handle_checkout_completed({})
    StripeService.handle_checkout_completed({"metadata": {}})


@pytest.mark.django_db
def test_handle_checkout_completed_order_not_found_or_already_paid(order):
    StripeService.handle_checkout_completed({"metadata": {"order_id": 99999}})

    order.status = Order.Status.PAID
    order.save()
    StripeService.handle_checkout_completed({"metadata": {"order_id": str(order.id)}})


@pytest.mark.django_db
def test_handle_checkout_completed_success_with_coupon_and_payment(order):
    uid = uuid.uuid4().hex[:8]
    tx_id = f"cs_test_hook_{uid}"

    coupon = Coupon.objects.create(
        code=f"SAVE_{uid[:4].upper()}",
        discount_percentage=10,
        valid_from="2026-01-01T00:00:00Z",
        valid_to="2026-12-31T23:59:59Z",
        times_used=0,
    )
    order.coupon = coupon
    order.save()

    payment = Payment.objects.create(
        order=order,
        provider=Payment.Provider.STRIPE,
        transaction_id=tx_id,
        status=Payment.Status.PENDING,
        amount=order.total_price,
    )

    session = {
        "id": tx_id,
        "metadata": {"order_id": str(order.id)},
    }

    with patch("django.db.transaction.on_commit", side_effect=lambda func: func()):
        with patch("store.tasks.send_order_confirmation_email.delay") as mock_email_delay:
            StripeService.handle_checkout_completed(session)

            order.refresh_from_db()
            assert order.status == Order.Status.PAID

            coupon.refresh_from_db()
            assert coupon.times_used == 1

            payment.refresh_from_db()
            assert payment.status == Payment.Status.PAID

            mock_email_delay.assert_called_once_with(order.id)


@pytest.mark.django_db
def test_stripe_webhook_view_signature_error():
    client = APIClient()
    url = reverse("stripe-webhook")

    with patch("store.services.stripe_service.StripeService.construct_webhook_event", side_effect=stripe.error.SignatureVerificationError("Invalid sig", "sig")):
        response = client.post(url, data=b"{}", content_type="application/json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_stripe_webhook_view_value_error():
    client = APIClient()
    url = reverse("stripe-webhook")

    with patch("store.services.stripe_service.StripeService.construct_webhook_event", side_effect=ValueError("Invalid payload")):
        response = client.post(url, data=b"{}", content_type="application/json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_stripe_webhook_view_checkout_completed_handled():
    client = APIClient()
    url = reverse("stripe-webhook")

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_webhook_event_1",
                "metadata": {"order_id": "123"},
            }
        },
    }

    with patch("store.services.stripe_service.StripeService.construct_webhook_event", return_value=event):
        with patch("store.services.stripe_service.StripeService.handle_checkout_completed") as mock_handle:
            response = client.post(url, data=b"{}", content_type="application/json")
            assert response.status_code == status.HTTP_200_OK
            mock_handle.assert_called_once_with(event["data"]["object"])


@pytest.mark.django_db
def test_stripe_webhook_view_ignored_event_type():
    client = APIClient()
    url = reverse("stripe-webhook")

    event = {"type": "payment_intent.created", "data": {"object": {}}}

    with patch("store.services.stripe_service.StripeService.construct_webhook_event", return_value=event):
        with patch("store.services.stripe_service.StripeService.handle_checkout_completed") as mock_handle:
            response = client.post(url, data=b"{}", content_type="application/json")
            assert response.status_code == status.HTTP_200_OK
            mock_handle.assert_not_called()