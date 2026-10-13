import uuid
from datetime import timedelta

from django.utils import timezone
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from store.models import Category, Product, ProductVariant, Address, Coupon, Wishlist, Order, OrderItem, Review, \
    Payment, OrderStatusHistory, ProductImage, Brand
from store.models.cart import Cart, CartItem

@pytest.fixture
def user():
    User = get_user_model()
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    return User.objects.create_user(
        email=unique_email,
        password="password123"
    )


@pytest.fixture
def category():
    uid = uuid.uuid4().hex[:6]
    return Category.objects.create(name=f"Shoes {uid}", slug=f"shoes-{uid}")


@pytest.fixture
def product(category):
    uid = uuid.uuid4().hex[:6]
    return Product.objects.create(
        category=category,
        name=f"Sneakers {uid}",
        slug=f"sneakers-{uid}",
    )

@pytest.fixture
def order(user):
    return Order.objects.create(
        user=user,
        shipping_address="123 Main St",
        contact_phone="+3901234567",
        contact_email="test@gmail.com",
    )

@pytest.fixture
def variant(product):
    uid = uuid.uuid4().hex[:6]
    return ProductVariant.objects.create(
        product=product,
        sku=f"SKU-{uid}",
        name="Red",
        price=Decimal("150.00"),
    )


@pytest.fixture
def cart():
    return Cart.objects.create()

@pytest.fixture
def address_data(user):
    return {
        "user": user,
        "first_name": "John",
        "last_name": "Doe",
        "country": "Italy",
        "city": "Rome",
        "street_address": "123 Main St",
        "postal_code": "00100",
        "phone_number": "+3901234567",
    }

@pytest.mark.django_db
def test_cart_str_for_authenticated_user(user):
    cart = Cart.objects.create(user=user)
    assert str(cart) == f"Cart ({user.email}) - #{cart.id}"


@pytest.mark.django_db
def test_cart_str_for_anonymous(cart):
    assert str(cart) == f"Cart (Anonymous) - #{cart.id}"


@pytest.mark.django_db
def test_cart_total_price_empty(cart):
    assert cart.total_price == 0


@pytest.mark.django_db
def test_cart_total_price_with_items(cart, product):
    uid = uuid.uuid4().hex[:4]
    variant1 = ProductVariant.objects.create(
        product=product,
        sku=f"SKU-1-{uid}",
        name="Red",
        price=Decimal("100.00"),
    )
    variant2 = ProductVariant.objects.create(
        product=product,
        sku=f"SKU-2-{uid}",
        name="Blue",
        price=Decimal("150.00"),
    )

    CartItem.objects.create(cart=cart, variant=variant1, quantity=2)
    CartItem.objects.create(cart=cart, variant=variant2, quantity=1)

    assert cart.total_price == Decimal("350.00")


@pytest.mark.django_db
def test_cart_item_subtotal_and_unit_price(cart, variant):
    item = CartItem.objects.create(cart=cart, variant=variant, quantity=3)

    assert item.unit_price == Decimal("150.00")
    assert item.subtotal == Decimal("450.00")


@pytest.mark.django_db
def test_cart_item_unique_together(cart, variant):
    CartItem.objects.create(cart=cart, variant=variant, quantity=1)

    with pytest.raises(IntegrityError):
        CartItem.objects.create(cart=cart, variant=variant, quantity=2)

@pytest.mark.django_db
def test_product_variant_str(variant):
    assert str(variant) == f"{variant.product.name} ({variant.name}) - {variant.sku}"

@pytest.mark.django_db
def test_product_variant_defaults(variant):
    assert variant.quantity == 0
    assert variant.is_active is True

@pytest.mark.django_db
def test_category_protected_on_product_delete(category, product):
    with pytest.raises(IntegrityError):
        category.delete()

@pytest.mark.django_db
def test_cannot_delete_variant_present_in_cart_item(cart, variant):
    CartItem.objects.create(cart=cart, variant=variant, quantity=1)
    with pytest.raises(IntegrityError):
        variant.delete()

@pytest.mark.django_db
def test_cart_item_str(variant):
    item = CartItem(quantity=2, variant=ProductVariant())
    assert str(item) == f"{item.quantity} x {item.variant.name}"

@pytest.mark.django_db
def test_delete_product_cascade_to_variants(product, variant):
    product.delete()
    assert not ProductVariant.objects.filter(id=variant.id).exists()

@pytest.mark.django_db
def test_cannot_create_duplicate_category_slug(category):
    with pytest.raises(IntegrityError):
        Category.objects.create(name="Another Shoes", slug=category.slug)

@pytest.mark.django_db
def test_address_set_default_resets_previous_default(user, address_data):
    addr1 = Address.objects.create(**address_data, is_default=True)
    assert addr1.is_default is True

    address_data["street_address"] = "456 Elm St"
    addr2 = Address.objects.create(**address_data, is_default=True)

    addr1.refresh_from_db()

    assert addr1.is_default is False
    assert addr2.is_default is True

@pytest.mark.django_db
def test_coupon_is_valid_success():
    now = timezone.now()
    coupon = Coupon.objects.create(
        code="FREE",
        discount_percentage=10,
        active=True,
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=30),
        usage_limit=10,
        times_used=0,
    )

    assert coupon.is_valid() is True

@pytest.mark.django_db
def test_coupon_is_valid_inactive():
    now = timezone.now()
    coupon = Coupon.objects.create(
        code="FREE",
        discount_percentage=10,
        active=False,
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=30),
        usage_limit=10,
        times_used=0,
    )
    assert coupon.is_valid() is False

@pytest.mark.django_db
def test_coupon_is_valid_expired():
    now = timezone.now()
    coupon = Coupon.objects.create(
        code="FREE",
        discount_percentage=10,
        active=True,
        valid_from=now - timedelta(days=31),
        valid_to=now - timedelta(days=1),
    )
    assert coupon.is_valid() is False

@pytest.mark.django_db
def test_coupon_is_valid_usage_limit_reached():
    now = timezone.now()
    coupon = Coupon.objects.create(
        code="LIMIT10",
        discount_percentage=10,
        active=True,
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=30),
        usage_limit=10,
        times_used=10,
    )
    assert coupon.is_valid() is False

@pytest.mark.django_db
def test_wishlist_unique_together(user, product):
    Wishlist.objects.create(user=user, product=product)
    with pytest.raises(IntegrityError):
        Wishlist.objects.create(user=user, product=product)

@pytest.mark.django_db
def test_order_item_cost(order, variant):
    item = OrderItem.objects.create(
        order=order,
        variant=variant,
        price=Decimal("150.00"),
        quantity=2,
    )
    assert item.cost == Decimal("300.00")

@pytest.mark.django_db
def test_review_unique_together(user, product):
    Review.objects.create(user=user, product=product, rating=5, comment="Great product!")
    with pytest.raises(IntegrityError):
        Review.objects.create(user=user, product=product, rating=5, comment="Great product!")

@pytest.mark.django_db
def test_brand_str_and_creation():
    uid = uuid.uuid4().hex[:6]
    brand = Brand.objects.create(name=f"Nike {uid}", slug=f"nike-{uid}", description="Sportswear")
    assert str(brand) == brand.name

@pytest.mark.django_db
def test_category_parent_and_children_relation():
    uid1, uid2 = uuid.uuid4().hex[:4], uuid.uuid4().hex[:4]
    parent = Category.objects.create(name=f"Clothes {uid1}", slug=f"clothes-{uid1}")
    child = Category.objects.create(name=f"Jackets {uid2}", slug=f"jackets-{uid2}", parent=parent)

    assert str(parent) == parent.name
    assert child.parent == parent
    assert child in parent.children.all()

@pytest.mark.django_db
def test_product_str(product):
    assert str(product) == product.name

@pytest.mark.django_db
def test_product_image_creation(product):
    image = ProductImage.objects.create(
        product=product,
        image="products/2026/test.png",
        is_feature=True,
        alt_text="Front view",
    )
    assert image.product == product
    assert image.is_feature is True
    assert image.alt_text == "Front view"

@pytest.mark.django_db
def test_address_str(user, address_data):
    addr = Address.objects.create(**address_data)
    assert str(addr) == f"{addr.street_address}, {addr.city}, {addr.country}"


@pytest.mark.django_db
def test_wishlist_str(user, product):
    item = Wishlist.objects.create(user=user, product=product)
    assert str(item) == f"{user} - {product.name}"

@pytest.mark.django_db
def test_order_str(order):
    assert str(order) == f"Order #{order.id} - {order.status}"


@pytest.mark.django_db
def test_order_item_str(order, variant):
    item = OrderItem.objects.create(
        order=order,
        variant=variant,
        price=Decimal("150.00"),
        quantity=3,
    )
    assert str(item) == f"{variant} x 3"

@pytest.mark.django_db
def test_order_status_history_creation_and_str(order):
    history = OrderStatusHistory.objects.create(
        order=order,
        old_status=Order.Status.PENDING,
        new_status=Order.Status.PAID,
        comment="Stripe payment received",
    )
    assert history.order == order
    assert str(history) == f"Order #{order.id}: pending -> paid"

@pytest.mark.django_db
def test_payment_creation_and_str(order):
    uid = uuid.uuid4().hex[:8]
    payment = Payment.objects.create(
        order=order,
        provider=Payment.Provider.STRIPE,
        transaction_id=f"tx_{uid}",
        status=Payment.Status.PAID,
        amount=Decimal("150.00"),
    )
    assert str(payment) == f"Payment tx_{uid} (stripe - paid)"
    assert payment.order == order

@pytest.mark.django_db
def test_coupon_str():
    now = timezone.now()
    valid_from = now - timedelta(days=1)
    valid_to = now + timedelta(days=10)
    coupon = Coupon.objects.create(
        code="PROMO15",
        discount_percentage=15,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    assert str(coupon) == f"PROMO15 - 15% off for {valid_from} - {valid_to}"

@pytest.mark.django_db
def test_review_str(user, product):
    review = Review.objects.create(
        user=user,
        product=product,
        rating=5,
        comment="Solid quality!",
    )
    assert str(review) == f"Review by {user} for {product.name} (5/5)"