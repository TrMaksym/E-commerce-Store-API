from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Coupon(models.Model):
    code = models.CharField(max_length=10)
    discount_percentage = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Discount percentage(1-100)",
    )
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=100)
    times_used = models.PositiveIntegerField(default=0)

    def is_valid(self):
        now = timezone.now()
        return (
            self.active
            and self.valid_from <= now <= self.valid_to
            and self.times_used < self.usage_limit
        )

    def __str__(self):
        return f"{self.code} - {self.discount_percentage}% off for {self.valid_from} - {self.valid_to}"


