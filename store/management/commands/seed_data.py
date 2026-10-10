from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from store.models import Brand, Category, Coupon, Product, ProductVariant

now = timezone.now()

class Command(BaseCommand):
    help = "Populate database with sample catalog data"

    def handle(self, *args, **options):
        self.stdout.write("Cleaning old catalog data...")
        ProductVariant.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Brand.objects.all().delete()
        Coupon.objects.all().delete()

        self.stdout.write("Creating brands and categories...")
        brands = {}
        for name in ["Krono", "Aurora", "Minimal"]:
            brands[name] = Brand.objects.create(name=name, slug=slugify(name))

        categories = {}
        for name in ["Bracelets", "Rings", "Necklaces"]:
            categories[name] = Category.objects.create(
                name=name, slug=slugify(name)
            )

        self.stdout.write("Creating sample coupons...")
        Coupon.objects.create(
            code="SAVE10",
            discount_percentage=10,
            active=True,
            valid_from=now,
            valid_to=now + timedelta(days=30),
        )

        Coupon.objects.create(
            code="SUMMER20",
            discount_percentage=20,
            active=True,
            valid_from=now,
            valid_to=now + timedelta(days=60),
        )

        self.stdout.write("Creating products and variants...")

        items = [
            {
                "name": "Classic Gold Cuff Bracelet",
                "brand": brands["Krono"],
                "category": categories["Bracelets"],
                "description": "Minimalist 18k gold plated cuff bracelet.",
                "variants": [
                    {"sku": "CBR-G-S", "price": Decimal("120.00"), "qty": 15},
                    {"sku": "CBR-G-M", "price": Decimal("140.00"), "qty": 0},
                ],
            },
            {
                "name": "Silver Wave Cuff",
                "brand": brands["Aurora"],
                "category": categories["Bracelets"],
                "description": "Polished sterling silver cuff with wave curve.",
                "variants": [
                    {"sku": "SWC-S", "price": Decimal("85.00"), "qty": 8},
                    {"sku": "SWC-L", "price": Decimal("95.00"), "qty": 5},
                ],
            },
            {
                "name": "Signet Minimal Ring",
                "brand": brands["Minimal"],
                "category": categories["Rings"],
                "description": "Subtle brushed signet ring.",
                "variants": [
                    {"sku": "SMR-16", "price": Decimal("45.00"), "qty": 0},
                    {"sku": "SMR-18", "price": Decimal("45.00"), "qty": 0},
                ],
            },
            {
                "name": "Slim Gold Chain Necklace",
                "brand": brands["Krono"],
                "category": categories["Necklaces"],
                "description": "Dainty everyday chain necklace in yellow gold finish.",
                "variants": [
                    {"sku": "SGN-45", "price": Decimal("180.00"), "qty": 12},
                    {"sku": "SGN-50", "price": Decimal("210.00"), "qty": 3},
                ],
            },
            {
                "name": "Draft Platinum Band",
                "brand": brands["Aurora"],
                "category": categories["Rings"],
                "description": "Unpublished product for staff testing.",
                "is_active": False,
                "variants": [
                    {"sku": "DPB-01", "price": Decimal("350.00"), "qty": 2},
                ],
            },
        ]

        for item_data in items:
            variants = item_data.pop("variants")
            product = Product.objects.create(
                slug=slugify(item_data["name"]), **item_data
            )
            for var in variants:
                ProductVariant.objects.create(
                    product=product,
                    sku=var["sku"],
                    price=var["price"],
                    quantity=var["qty"],
                )

        self.stdout.write(
            self.style.SUCCESS("Database seeded successfully with sample data!")
        )