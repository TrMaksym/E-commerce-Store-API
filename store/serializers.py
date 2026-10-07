from rest_framework import serializers

from store.models import Category, Brand, ProductVariant, ProductImage, Address, Wishlist, Product, Order, OrderItem, \
    OrderStatusHistory, Payment, Coupon, Review


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


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)


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
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ("id", "product", "created_at")

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
            "created_at"
        )
        read_only_fields = fields


class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = ("id", "code", "discount_percentage", "valid_from", "valid_to", "is_valid")

    def get_is_valid(self, obj):
        return obj.is_valid()

    def validate(self, attrs):
        valid_from = attrs.get("valid_from") or (self.instance.valid_from if self.instance else None)
        valid_to = attrs.get("valid_to") or (self.instance.valid_to if self.instance else None)

        if valid_from and valid_to:
            if valid_from >= valid_to:
                raise serializers.ValidationError({"valid_to": "Valid from date must be before valid to date."})
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.email")

    class Meta:
        model = Review
        fields = ("id", "product", "user", "rating", "comment", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")
