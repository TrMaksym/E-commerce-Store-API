import uuid
from decimal import Decimal
import pytest
from store.filters import ProductFilter
from store.models import Brand, Category, Product, ProductVariant

@pytest.fixture
def category():
    uid = uuid.uuid4().hex[:6]
    return Category.objects.create(name=f"Cat {uid}", slug=f"cat-{uid}")

@pytest.fixture
def brand():
    uid = uuid.uuid4().hex[:6]
    return Brand.objects.create(name=f"Brand {uid}", slug=f"brand-{uid}")

@pytest.mark.django_db
def test_product_filter_price_and_category_and_brand(category, brand):
    uid1, uid2 = uuid.uuid4().hex[:4], uuid.uuid4().hex[:4]
    cat2 = Category.objects.create(name=f"Cat {uid2}", slug=f"cat2-{uid2}")

    p1 = Product.objects.create(category=category, brand=brand, name="P1", slug=f"p1-{uid1}")
    p2 = Product.objects.create(category=cat2, brand=brand, name="P2", slug=f"p2-{uid2}")

    ProductVariant.objects.create(product=p1, sku=f"S1-{uid1}", name="V1", price=Decimal("50.00"), quantity=5)
    ProductVariant.objects.create(product=p2, sku=f"S2-{uid2}", name="V2", price=Decimal("150.00"), quantity=2)

    qs = Product.objects.all()

    f_min = ProductFilter({"min_price": "100.00"}, queryset=qs)
    assert p2 in f_min.qs
    assert p1 not in f_min.qs

    f_max = ProductFilter({"max_price": "100.00"}, queryset=qs)
    assert p1 in f_max.qs
    assert p2 not in f_max.qs

    f_cat = ProductFilter({"category": category.id}, queryset=qs)
    assert p1 in f_cat.qs
    assert p2 not in f_cat.qs

    f_brand = ProductFilter({"brand": brand.id}, queryset=qs)
    assert f_brand.qs.count() == 2

@pytest.mark.django_db
def test_product_filter_in_stock(category):
    uid1, uid2 = uuid.uuid4().hex[:4], uuid.uuid4().hex[:4]
    p_instock = Product.objects.create(category=category, name="InStock", slug=f"is-{uid1}")
    p_outstock = Product.objects.create(category=category, name="OutStock", slug=f"os-{uid2}")

    ProductVariant.objects.create(product=p_instock, sku=f"SKU-IS-{uid1}", name="V1", price=Decimal("20.00"), quantity=3)
    ProductVariant.objects.create(product=p_outstock, sku=f"SKU-OS-{uid2}", name="V2", price=Decimal("20.00"), quantity=0)

    qs = Product.objects.all()

    f_true = ProductFilter({"in_stock": True}, queryset=qs)
    assert p_instock in f_true.qs
    assert p_outstock not in f_true.qs

    f_false = ProductFilter({"in_stock": False}, queryset=qs)
    assert p_outstock in f_false.qs
    assert p_instock not in f_false.qs

    f_none = ProductFilter({}, queryset=qs)
    assert f_none.qs.count() >= 2