from decimal import Decimal
from django.conf import settings
from django.db import models

from .catalog import ProductVariant
from .promotions import Coupon


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        PAID = "paid", "paid"
        SHIPPED = "shipped", "shipped"
        DELIVERED = "delivered", "delivered"
        CANCELED = "canceled", "canceled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    shipping_address = models.TextField(help_text="address")
    contact_phone = models.CharField(max_length=32)
    contact_email = models.EmailField()

    subtotal_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="order_items"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="fix price for each item",
    )
    quantity = models.PositiveIntegerField(default=1)

    @property
    def cost(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.variant} x {self.quantity}"

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    old_status = models.CharField(max_length=20, choices=Order.Status.choices)
    new_status = models.CharField(max_length=20, choices=Order.Status.choices)
    changed_at = models.DateTimeField(auto_now_add=True)
    comment = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Order #{self.order_id}: {self.old_status} -> {self.new_status}"
