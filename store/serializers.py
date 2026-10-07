from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from store.models import (
    Category,
    Brand,
    ProductVariant,
    ProductImage,
    Address,
    Wishlist,
    Product,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    Coupon,
    Review,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "slug", "description")


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ("id", "sku", "name", "price", "quantity", "is_active")


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "is_feature", "alt_text")


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="Brand.name", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "is_active",
            "category_name",
            "brand_name",
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(source="Brand", read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "category",
            "brand",
            "variants",
            "images",
            "created_at",
            "updated_at",
        )


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "first_name",
            "last_name",
            "country",
            "city",
            "street_address",
            "postal_code",
            "phone_number",
            "is_default",
        )

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True, source="product"
    )

    class Meta:
        model = Wishlist
        fields = ("id", "product", "product_id", "created_at")

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "variant", "price", "quantity", "cost")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "user",
            "status",
            "coupon",
            "shipping_address",
            "contact_phone",
            "contact_email",
            "subtotal_price",
            "discount_amount",
            "total_price",
            "items",
            "created_at",
        )


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ("id", "old_status", "new_status", "changed_at", "comment")


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "order",
            "provider",
            "transaction_id",
            "status",
            "amount",
            "created_at",
        )
        read_only_fields = fields


class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = (
            "id",
            "code",
            "discount_percentage",
            "valid_from",
            "valid_to",
            "is_valid",
        )

    def get_is_valid(self, obj):
        return obj.is_valid()

    def validate(self, attrs):
        valid_from = attrs.get("valid_from") or (
            self.instance.valid_from if self.instance else None
        )
        valid_to = attrs.get("valid_to") or (
            self.instance.valid_to if self.instance else None
        )

        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError(
                {"valid_to": "Valid from date must be before valid to date."}
            )
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.email")

    class Meta:
        model = Review
        fields = (
            "id",
            "product",
            "user",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class CheckoutItemSerializer(serializers.Serializer):
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
        source="variant"
    )
    quantity = serializers.IntegerField(min_value=1)


class CheckoutSerializer(serializers.Serializer):
    shipping_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all(),
        source="shipping_address"
    )
    contact_phone = serializers.CharField(max_length=20)
    contact_email = serializers.EmailField()
    coupon_code = serializers.CharField(required=False, allow_blank=True)
    items = CheckoutItemSerializer(many=True)

    def validate_items(self, items):
        if len(items) == 0:
            raise serializers.ValidationError("Cart cannot be empty.")

        for item in items:
            variant = item["variant"]
            quantity = item["quantity"]

            if quantity <= 0:
                raise serializers.ValidationError(f"Quantity for variant {variant.id} must be greater than 0.")
            if variant.quantity < quantity:
                raise serializers.ValidationError(f"Insufficient quantity for variant {variant.id}. Available: {variant.quantity}.")

        return items

    def create(self, validated_data):
        items = validated_data.pop("items")
        coupon_code = validated_data.pop("coupon_code", None)
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None

        subtotal_price = sum(item["variant"].price * item["quantity"] for item in items)
        discount_amount = 0
        coupon = None

        if coupon_code:
            try:
                found_coupon = Coupon.objects.get(code=coupon_code)
                if found_coupon.is_valid():
                    coupon = found_coupon
                    discount_amount = round(
                        (subtotal_price * Decimal(found_coupon.discount_percentage)) / Decimal(100),
                        2
                    )
            except Coupon.DoesNotExist:
                pass

        total_price = subtotal_price - discount_amount

        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                coupon=coupon,
                subtotal_price=subtotal_price,
                discount_amount=discount_amount,
                total_price=total_price,
                status=Order.Status.PENDING,
                **validated_data
            )
            for item in items:
                variant = item["variant"]
                quantity = item["quantity"]

                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    price=variant.price,
                    quantity=quantity,
                    cost=variant.price * quantity
                )

                variant.quantity -= quantity
                variant.save(update_fields=["quantity"])
            return order

