from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=120, db_index=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
    )
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(
        max_length=120, help_text="Example: Size: Medium, Color: Blue"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} ({self.name}) - {self.sku}"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/%Y/%m/")
    is_feature = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=255, blank=True)