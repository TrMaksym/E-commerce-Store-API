import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from store.models import Category, Order, OrderItem, Product, ProductVariant
from store.tasks import cancel_expired_orders, send_order_confirmation_email

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
    return Product.objects.create(category=cat, name=f"Prod {uid}", slug=f"prod-{uid}")


@pytest.fixture
def variant(product):
    uid = uuid.uuid4().hex[:6]
    return ProductVariant.objects.create(
        product=product,
        sku=f"SKU-{uid}",
        name="Size L",
        price=Decimal("50.00"),
        quantity=10,
    )


@pytest.mark.django_db
def test_send_order_confirmation_email_not_found():
    result = send_order_confirmation_email(99999)
    assert result == "Order #99999 not found or no contact email provided"


@pytest.mark.django_db
def test_send_order_confirmation_email_no_contact_email(user):
    order = Order.objects.create(
        user=user,
        shipping_address="Address 1",
        contact_phone="+3901234567",
        contact_email="",
    )
    result = send_order_confirmation_email(order.id)
    assert result == f"Order #{order.id} not found or no contact email provided"


@pytest.mark.django_db
def test_send_order_confirmation_email_success(user):
    order = Order.objects.create(
        user=user,
        shipping_address="Address 1",
        contact_phone="+3901234567",
        contact_email="customer@example.com",
        total_price=Decimal("150.00"),
        status=Order.Status.PENDING,
    )

    with patch("store.tasks.send_mail") as mock_send:
        result = send_order_confirmation_email(order.id)
        assert result == f"Confirmation sent for Order #{order.id}"
        mock_send.assert_called_once()
        assert mock_send.call_args[1]["recipient_list"] == ["customer@example.com"]
        assert f"#{order.id}" in mock_send.call_args[1]["subject"]


@pytest.mark.django_db
def test_cancel_expired_orders(user, variant):
    Order.objects.all().delete()
    old_time = timezone.now() - timedelta(hours=25)

    expired_order = Order.objects.create(
        user=user,
        status=Order.Status.PENDING,
        shipping_address="Address 1",
        contact_phone="+3901234567",
        contact_email=user.email,
    )
    Order.objects.filter(id=expired_order.id).update(created_at=old_time)

    OrderItem.objects.create(
        order=expired_order,
        variant=variant,
        price=variant.price,
        quantity=3,
    )

    fresh_order = Order.objects.create(
        user=user,
        status=Order.Status.PENDING,
        shipping_address="Address 2",
        contact_phone="+3901234567",
        contact_email=user.email,
    )
    OrderItem.objects.create(
        order=fresh_order,
        variant=variant,
        price=variant.price,
        quantity=2,
    )

    paid_old_order = Order.objects.create(
        user=user,
        status=Order.Status.PAID,
        shipping_address="Address 3",
        contact_phone="+3901234567",
        contact_email=user.email,
    )
    Order.objects.filter(id=paid_old_order.id).update(created_at=old_time)

    result = cancel_expired_orders()
    assert result == "Canceled 1 expired orders"

    expired_order.refresh_from_db()
    assert expired_order.status == Order.Status.CANCELED

    fresh_order.refresh_from_db()
    assert fresh_order.status == Order.Status.PENDING

    paid_old_order.refresh_from_db()
    assert paid_old_order.status == Order.Status.PAID

    variant.refresh_from_db()
    assert variant.quantity == 13