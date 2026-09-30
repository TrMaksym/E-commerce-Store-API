from django.db import transaction
from redis.commands.search.reducers import quantile
from rest_framework import serializers

from store.models import Product, OrderItem, Order


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "price", "description", "amount", "created_at", ]

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "quantity",
            "price",
            "total_cost_one_position",
        ]
        read_only_fields = ["total_cost_one_position", "price"]

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "first_name",
            "last_name",
            "email",
            "address",
            "status",
            "items",
            "total_price",
            "created_at",
        ]
        read_only_fields = ["user", "status", "total_price", "created_at"]

        @transaction.atomic
        def create(self, validated_data):
            items_data = validated_data.pop("items")
            order = Order.objects.create(total_price=0, **validated_data)
            total_price = 0
            order_items = []

            for item in items_data:
                product = item["product"]
                quantity = item["quantity"]

                if product.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient quantity for product {product.name}"
                    )

                product.quantity -= quantity
                product.save(update_fields=["quantity"])

                total_price += product.price * quantity

                order_items.append(
                    OrderItem(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price,
                    )
                )
            OrderItem.object.bulk_create(order_items)
            order.total_price = total_price
            order.save(update_fields=["total_price"])

            return order



