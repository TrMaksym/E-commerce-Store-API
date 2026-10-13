import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from config import settings
from store.models import (
    Address,
    Brand,
    Category,
    Coupon,
    Order,
    Product,
    ProductVariant,
    Review, OrderItem,
)
from store.models.cart import Cart, CartItem

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    uid = uuid.uuid4().hex[:6]
    return User.objects.create_user(
        email=f"user_{uid}@example.com",
        password="password123",
    )


@pytest.fixture
def admin_user():
    uid = uuid.uuid4().hex[:6]
    return User.objects.create_user(
        email=f"admin_{uid}@example.com",
        password="password123",
        is_staff=True,
    )


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def category():
    uid = uuid.uuid4().hex[:6]
    return Category.objects.create(name=f"Shoes {uid}", slug=f"shoes-{uid}")


@pytest.fixture
def brand():
    uid = uuid.uuid4().hex[:6]
    return Brand.objects.create(name=f"Brand {uid}", slug=f"brand-{uid}")


@pytest.fixture
def product(category, brand):
    uid = uuid.uuid4().hex[:6]
    return Product.objects.create(
        category=category,
        brand=brand,
        name=f"Sneakers {uid}",
        slug=f"sneakers-{uid}",
        is_active=True,
    )


@pytest.fixture
def variant(product):
    uid = uuid.uuid4().hex[:6]
    return ProductVariant.objects.create(
        product=product,
        sku=f"SKU-{uid}",
        name="Red",
        price=Decimal("150.00"),
        quantity=5,
    )


@pytest.fixture
def coupon():
    uid = uuid.uuid4().hex[:4].upper()
    now = timezone.now()
    return Coupon.objects.create(
        code=f"SALE{uid}",
        discount_percentage=15,
        active=True,
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=10),
        usage_limit=5,
        times_used=0,
    )


@pytest.fixture
def order(user):
    return Order.objects.create(
        user=user,
        shipping_address="123 Main St",
        contact_phone="+3901234567",
        contact_email=user.email,
        status=Order.Status.PENDING,
    )


@pytest.mark.django_db
def test_cart_requires_authentication(api_client):
    url = reverse("cart-list")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_cart_get_creates_and_returns_cart(auth_client, user):
    url = reverse("cart-list")
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert Cart.objects.filter(user=user).exists()
    assert response.data["items"] == []


@pytest.mark.django_db
def test_cart_add_new_item_success(auth_client, user, variant):
    url = reverse("cart-add")
    payload = {
        "variant_id": variant.id,
        "quantity": 2,
    }

    response = auth_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    cart = Cart.objects.get(user=user)
    assert cart.items.count() == 1
    assert cart.items.first().quantity == 2


@pytest.mark.django_db
def test_cart_add_existing_item_increases_quantity(auth_client, user, variant):
    url = reverse("cart-add")
    payload = {
        "variant_id": variant.id,
        "quantity": 2,
    }

    auth_client.post(url, payload, format="json")
    response = auth_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    cart = Cart.objects.get(user=user)
    assert cart.items.first().quantity == 4


@pytest.mark.django_db
def test_cart_add_exceeding_stock_fails(auth_client, variant):
    url = reverse("cart-add")
    payload = {
        "variant_id": variant.id,
        "quantity": 3,
    }
    auth_client.post(url, payload, format="json")

    response = auth_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "available in stock" in response.data["detail"]


@pytest.mark.django_db
def test_cart_remove_item_success(auth_client, user, variant):
    cart, _ = Cart.objects.get_or_create(user=user)
    item = CartItem.objects.create(cart=cart, variant=variant, quantity=1)

    url = reverse("cart-remove-item", kwargs={"item_id": item.id})
    response = auth_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not CartItem.objects.filter(id=item.id).exists()


@pytest.mark.django_db
def test_cart_remove_nonexistent_item_returns_404(auth_client):
    url = reverse("cart-remove-item", kwargs={"item_id": 99999})
    response = auth_client.delete(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_cart_clear_success(auth_client, user, variant):
    cart, _ = Cart.objects.get_or_create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=2)

    url = reverse("cart-clear")
    response = auth_client.post(url)

    assert response.status_code == status.HTTP_200_OK
    assert cart.items.count() == 0


@pytest.mark.django_db
def test_product_list_public_only_shows_active(api_client, category):
    uid = uuid.uuid4().hex[:6]
    Product.objects.create(category=category, name="Active Prod", slug=f"act-{uid}", is_active=True)
    Product.objects.create(category=category, name="Inactive Prod", slug=f"inact-{uid}", is_active=False)

    url = reverse("products-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    slugs = [p["slug"] for p in response.data["results"]] if "results" in response.data else [p["slug"] for p in response.data]
    assert f"act-{uid}" in slugs
    assert f"inact-{uid}" not in slugs


@pytest.mark.django_db
def test_product_list_staff_sees_inactive(admin_client, category):
    uid = uuid.uuid4().hex[:6]
    Product.objects.create(category=category, name="Inactive Prod", slug=f"inact-{uid}", is_active=False)

    url = reverse("products-list")
    response = admin_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    slugs = [p["slug"] for p in response.data["results"]] if "results" in response.data else [p["slug"] for p in response.data]
    assert f"inact-{uid}" in slugs


@pytest.mark.django_db
def test_product_detail_retrieve(api_client, product):
    url = reverse("products-detail", kwargs={"pk": product.id})
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == product.id
    assert response.data["name"] == product.name


@pytest.mark.django_db
def test_product_create_forbidden_for_regular_user(auth_client, category):
    url = reverse("products-list")
    payload = {"name": "Hacked", "slug": "hacked", "category": category.id}
    response = auth_client.post(url, payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_coupon_validate_success(api_client, coupon):
    url = reverse("coupons-validate")
    response = api_client.post(url, {"code": coupon.code}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["code"] == coupon.code
    assert response.data["discount_percentage"] == coupon.discount_percentage


@pytest.mark.django_db
def test_coupon_validate_missing_code_returns_400(api_client):
    url = reverse("coupons-validate")
    response = api_client.post(url, {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Coupon code is required."


@pytest.mark.django_db
def test_coupon_validate_nonexistent_returns_404(api_client):
    url = reverse("coupons-validate")
    response = api_client.post(url, {"code": "DOESNOTEXIST"}, format="json")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["detail"] == "Invalid coupon code."


@pytest.mark.django_db
def test_coupon_validate_inactive_or_expired_returns_400(api_client):
    now = timezone.now()
    coupon = Coupon.objects.create(
        code="EXPIRED_CODE",
        discount_percentage=10,
        active=False,
        valid_from=now - timedelta(days=10),
        valid_to=now - timedelta(days=1),
    )
    url = reverse("coupons-validate")
    response = api_client.post(url, {"code": coupon.code}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Coupon is expired or inactive."


@pytest.mark.django_db
def test_order_direct_post_disallowed(auth_client):
    url = reverse("orders-list")
    response = auth_client.post(url, {})

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert "Use the cart checkout flow" in response.data["detail"]


@pytest.mark.django_db
def test_order_list_user_sees_only_own_orders(auth_client, user, order):
    uid = uuid.uuid4().hex[:6]
    other_user = User.objects.create_user(
        email=f"other_{uid}@example.com",
        password="pwd",
    )
    Order.objects.create(
        user=other_user,
        shipping_address="456 Other St",
        contact_phone="+3909876543",
        contact_email=other_user.email,
    )

    url = reverse("orders-list")
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    orders = response.data["results"] if "results" in response.data else response.data
    assert len(orders) == 1
    assert orders[0]["id"] == order.id


@pytest.mark.django_db
def test_order_user_cannot_delete_order(auth_client, order):
    url = reverse("orders-detail", kwargs={"pk": order.id})
    response = auth_client.delete(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_order_staff_can_delete_order(admin_client, order):
    url = reverse("orders-detail", kwargs={"pk": order.id})
    response = admin_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Order.objects.filter(id=order.id).exists()


@pytest.mark.django_db
def test_order_checkout_already_paid_fails(auth_client, order):
    order.status = Order.Status.PAID
    order.save()

    url = reverse("orders-checkout", kwargs={"pk": order.id})
    response = auth_client.post(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "This order is already paid."


@pytest.mark.django_db
def test_order_checkout_success(auth_client, user, order, variant):
    settings.STRIPE_SUCCESS_URL = "http://testserver/success"
    settings.STRIPE_CANCEL_URL = "http://testserver/cancel"

    OrderItem.objects.create(
        order=order,
        variant=variant,
        price=Decimal("150.00"),
        quantity=1,
    )
    order.refresh_from_db()

    uid = uuid.uuid4().hex[:8]
    mock_session = MagicMock()
    mock_session.id = f"cs_test_{uid}"
    mock_session.url = f"https://checkout.stripe.com/pay/cs_test_{uid}"

    url = reverse("orders-checkout", kwargs={"pk": order.id})

    with patch("store.views.StripeService.create_checkout_session", return_value=mock_session):
        response = auth_client.post(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["checkout_url"] == mock_session.url


@pytest.mark.django_db
def test_review_create_authenticated(auth_client, user, product, variant):
    paid_order = Order.objects.create(
        user=user,
        shipping_address="123 Main St",
        contact_phone="+3901234567",
        contact_email=user.email,
        status=Order.Status.PAID,
    )
    OrderItem.objects.create(
        order=paid_order,
        variant=variant,
        price=variant.price,
        quantity=1,
    )

    url = reverse("reviews-list")
    payload = {
        "product": product.id,
        "rating": 5,
        "comment": "Awesome sneakers!",
    }
    response = auth_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert Review.objects.filter(user=user, product=product).exists()


@pytest.mark.django_db
def test_review_filter_by_product_id(api_client, user, product, category):
    uid = uuid.uuid4().hex[:6]
    prod2 = Product.objects.create(
        category=category,
        name=f"Shoes 2 {uid}",
        slug=f"shoes-2-{uid}",
        is_active=True,
    )
    Review.objects.create(user=user, product=product, rating=5, comment="Nice 1")
    Review.objects.create(user=user, product=prod2, rating=4, comment="Nice 2")

    url = f"{reverse('reviews-list')}?product_id={product.id}"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    reviews = response.data["results"] if "results" in response.data else response.data
    assert len(reviews) == 1
    assert reviews[0]["product"] == product.id


@pytest.mark.django_db
def test_address_create_assigns_authenticated_user(auth_client, user):
    url = reverse("addresses-list")
    payload = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "country": "Italy",
        "city": "Milan",
        "street_address": "Via Roma 1",
        "postal_code": "20121",
        "phone_number": "+39021234567",
        "is_default": True,
    }
    response = auth_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert Address.objects.filter(user=user, street_address="Via Roma 1").exists()