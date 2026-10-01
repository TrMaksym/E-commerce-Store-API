from django.db import models
from .orders import Order

class Payment(models.Model):
    class Provider(models.TextChoices):
        STRIPE = "stripe"
        LIQPAY = "liqpay"
        PAYPAL = "paypal"

    class Status(models.TextChoices):
        PENDING = "pending"
        PAID = "paid"
        FAILED = "failed"
        REFUNDED = "refunded"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=10, choices=Provider.choices)
    transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)
    payload = models.JSONField(null=True, blank=True, help_text="Payment provider response")

    def __str__(self):
        return f"Payment {self.transaction_id} ({self.provider} - {self.status})"

