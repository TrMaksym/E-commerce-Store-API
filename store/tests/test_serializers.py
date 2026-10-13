import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from store.models import (
    Address,
    Brand,
    Category,
    Coupon,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    Product,
    ProductImage,
    ProductVariant,
    Review,
    Wishlist,
)
from store.models.cart import Cart, CartItem
from store.serializers import (
    AddToCartSerializer,
    AddressSerializer,
    BrandSerializer,
    CartSerializer,
    CategorySerializer,
    CheckoutSerializer,
    CouponSerializer,
    OrderItemSerializer,
    OrderSerializer,
    OrderStatusHistorySerializer,
    PaymentSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
    ReviewSerializer,
    WishlistSerializer,
)

User = get_user_model()
factory = APIRequestFactory()


@pytest.fixture
def user():
    uid = uuid.uuid4().hex[:6]
    return User.objects.create_user(
        email=f"user_{uid}@example.com",
        password="password123",
    )


@pytest.fixture
def staff_user():
    uid = uuid.uuid4().hex[:6]
    return User.objects.create_user(
        email=f"staff_{uid}@example.com",
        password="password123",
        is_staff=True,
    )


@pytest.fixture
def category():
    uid = uuid.uuid4().hex[:6]
    return Category.objects.create(name=f"Shoes {uid}", slug=f"shoes-{uid}")


@pytest.fixture
def brand():
    uid = uuid.uuid4().hex[:6]
    return Brand.objects.create(name=f"Nike {uid}", slug=f"nike-{uid}")


@pytest.fixture
def product(category, brand):
    uid = uuid.uuid4().hex[:6]
    return Product.objects.create(
        category=category,
        brand=brand,
        name=f"Sneakers {uid}",
        slug=f"sneakers-{uid}",
        description="Comfortable",
        is_active=True,
    )


@pytest.fixture
def variant(product):
    uid = uuid.uuid4().hex[:6]
    return ProductVariant.objects.create(
        product=product,
        sku=f"SKU-{uid}",
        name="Size 42",
        price=Decimal("100.00"),
        quantity=10,
        is_active=True,
    )


@pytest.fixture
def address(user):
    return Address.objects.create(
        user=user,
        first_name="Mario",
        last_name="Rossi",
        country="Italy",
        city="Milan",
        street_address="Via Roma 1",
        postal_code="20121",
        phone_number="+39021234567",
        is_default=True,
    )


@pytest.fixture
def coupon():
    uid = uuid.uuid4().hex[:4].upper()
    now = timezone.now()
    return Coupon.objects.create(
        code=f"SALE{uid}",
        discount_percentage=20,
        active=True,
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=10),
        usage_limit=10,
        times_used=0,
    )


@pytest.fixture
def order_with_items(user, variant):
    order = Order.objects.create(
        user=user,
        shipping_address="Address 1",
        contact_phone="+3901234567",
        contact_email=user.email,
        subtotal_price=Decimal("200.00"),
        total_price=Decimal("200.00"),
    )
    OrderItem.objects.create(order=order, variant=variant, price=Decimal("100.00"), quantity=2)
    return order


@pytest.mark.django_db
def test_category_and_brand_serializers(category, brand):
    cat_data = CategorySerializer(category).data
    assert cat_data["name"] == category.name
    assert cat_data["slug"] == category.slug

    brand_data = BrandSerializer(brand).data
    assert brand_data["name"] == brand.name
    assert brand_data["slug"] == brand.slug


@pytest.mark.django_db
def test_product_variants_and_images_serializers(product, variant):
    ProductImage.objects.create(product=product, image="test.png", is_feature=True, alt_text="alt")

    v_data = ProductVariantSerializer(variant).data
    assert v_data["sku"] == variant.sku
    assert Decimal(v_data["price"]) == Decimal("100.00")

    detail_data = ProductDetailSerializer(product).data
    assert len(detail_data["variants"]) == 1
    assert len(detail_data["images"]) == 1

    list_data = ProductListSerializer(product).data
    assert list_data["name"] == product.name
    assert list_data["category_name"] == product.category.name
    assert list_data["brand_name"] == product.brand.name


@pytest.mark.django_db
def test_order_and_history_and_payment_serializers(user, order_with_items):
    order = order_with_items
    order_data = OrderSerializer(order).data
    assert len(order_data["items"]) == 1
    assert Decimal(order_data["items"][0]["cost"]) == Decimal("200.00")

    history = OrderStatusHistory.objects.create(
        order=order, old_status=Order.Status.PENDING, new_status=Order.Status.PAID, comment="Done"
    )
    hist_data = OrderStatusHistorySerializer(history).data
    assert hist_data["new_status"] == Order.Status.PAID

    payment = Payment.objects.create(
        order=order,
        provider="stripe",
        transaction_id=f"tx_{uuid.uuid4().hex[:8]}",
        status="paid",
        amount=order.total_price,
    )
    pay_data = PaymentSerializer(payment).data
    assert pay_data["amount"] == str(order.total_price)


@pytest.mark.django_db
def test_address_serializer_create(user):
    request = factory.post("/api/addresses/")
    request.user = user

    data = {
        "first_name": "Luigi",
        "last_name": "Verdi",
        "country": "Italy",
        "city": "Naples",
        "street_address": "Via Toledo 2",
        "postal_code": "80134",
        "phone_number": "+39081123456",
        "is_default": False,
    }
    serializer = AddressSerializer(data=data, context={"request": request})
    assert serializer.is_valid(), serializer.errors
    saved_address = serializer.save()
    assert saved_address.user == user


@pytest.mark.django_db
def test_wishlist_serializer_create(user, product):
    request = factory.post("/api/wishlist/")
    request.user = user

    serializer = WishlistSerializer(data={"product_id": product.id}, context={"request": request})
    assert serializer.is_valid(), serializer.errors
    item = serializer.save()
    assert item.user == user
    assert item.product == product


@pytest.mark.django_db
def test_coupon_serializer_dates_validation():
    now = timezone.now()
    serializer = CouponSerializer(
        data={
            "code": "BADCOUPON",
            "discount_percentage": 10,
            "valid_from": now,
            "valid_to": now - timedelta(days=1),
        }
    )
    assert not serializer.is_valid()
    assert "valid_to" in serializer.errors


@pytest.mark.django_db
def test_review_serializer_validation_already_reviewed(user, product, variant):
    order = Order.objects.create(
        user=user,
        status=Order.Status.PAID,
        shipping_address="A",
        contact_phone="1",
        contact_email=user.email,
    )
    OrderItem.objects.create(order=order, variant=variant, price=variant.price, quantity=1)
    Review.objects.create(user=user, product=product, rating=5, comment="First review")

    request = factory.post("/api/reviews/")
    request.user = user

    serializer = ReviewSerializer(
        data={"product": product.id, "rating": 4, "comment": "Second attempt"},
        context={"request": request},
    )
    assert not serializer.is_valid()
    assert "You have already reviewed this product" in str(serializer.errors)


@pytest.mark.django_db
def test_add_to_cart_serializer_variant_not_found():
    serializer = AddToCartSerializer(data={"variant_id": 99999, "quantity": 1})
    assert not serializer.is_valid()
    assert "Variant not found" in str(serializer.errors)


@pytest.mark.django_db
def test_add_to_cart_serializer_exceeding_stock(variant):
    serializer = AddToCartSerializer(data={"variant_id": variant.id, "quantity": 999})
    assert not serializer.is_valid()
    assert "available" in str(serializer.errors)


@pytest.mark.django_db
def test_checkout_cannot_use_another_users_address(user, address, variant):
    uid = uuid.uuid4().hex[:6]
    other_user = User.objects.create_user(email=f"other_{uid}@example.com", password="password123")
    request = factory.post("/api/orders/checkout/")
    request.user = other_user

    serializer = CheckoutSerializer(
        data={
            "shipping_id": address.id,
            "contact_phone": "+3901234567",
            "contact_email": "other@example.com",
            "items": [{"variant_id": variant.id, "quantity": 1}],
        },
        context={"request": request},
    )
    assert not serializer.is_valid()
    assert "shipping_id" in serializer.errors


@pytest.mark.django_db
def test_checkout_empty_items_and_empty_cart(user, address):
    request = factory.post("/api/orders/checkout/")
    request.user = user

    serializer = CheckoutSerializer(
        data={
            "shipping_id": address.id,
            "contact_phone": "+3901234567",
            "contact_email": user.email,
        },
        context={"request": request},
    )
    assert not serializer.is_valid()
    assert "Your cart is empty" in str(serializer.errors)


@pytest.mark.django_db
def test_checkout_success_direct_items_with_coupon_and_stock_reduction(user, address, variant, coupon):
    initial_stock = variant.quantity
    request = factory.post("/api/orders/checkout/")
    request.user = user

    serializer = CheckoutSerializer(
        data={
            "shipping_id": address.id,
            "contact_phone": "+3901234567",
            "contact_email": user.email,
            "coupon_code": coupon.code,
            "items": [{"variant_id": variant.id, "quantity": 2}],
        },
        context={"request": request},
    )
    assert serializer.is_valid(), serializer.errors
    order = serializer.save()

    assert order.user == user
    assert order.coupon == coupon
    assert order.subtotal_price == Decimal("200.00")
    assert order.discount_amount == Decimal("40.00")
    assert order.total_price == Decimal("160.00")

    variant.refresh_from_db()
    assert variant.quantity == initial_stock - 2


@pytest.mark.django_db
def test_checkout_from_cart_clears_cart(user, address, variant):
    cart, _ = Cart.objects.get_or_create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=3)

    request = factory.post("/api/orders/checkout/")
    request.user = user

    serializer = CheckoutSerializer(
        data={
            "shipping_id": address.id,
            "contact_phone": "+3901234567",
            "contact_email": user.email,
        },
        context={"request": request},
    )
    assert serializer.is_valid(), serializer.errors
    order = serializer.save()

    assert order.items.count() == 1
    assert order.items.first().quantity == 3
    assert cart.items.count() == 0