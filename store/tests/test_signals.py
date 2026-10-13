import uuid
from unittest.mock import patch
import pytest
from django.core.cache import cache
from store.models import Brand, Category, Product

@pytest.fixture
def category():
    uid = uuid.uuid4().hex[:6]
    return Category.objects.create(name=f"Cat {uid}", slug=f"cat-{uid}")

@pytest.fixture
def brand():
    uid = uuid.uuid4().hex[:6]
    return Brand.objects.create(name=f"Brand {uid}", slug=f"brand-{uid}")

@pytest.fixture
def product(category, brand):
    uid = uuid.uuid4().hex[:6]
    return Product.objects.create(
        category=category,
        brand=brand,
        name=f"Product {uid}",
        slug=f"prod-{uid}",
    )

@pytest.mark.django_db
def test_signals_cache_clear_fallback(category, brand, product):
    with patch.object(cache, "clear") as mock_clear:
        if hasattr(cache, "delete_pattern"):
            delattr(cache, "delete_pattern")

        Category.objects.create(name="Shoes", slug=f"shoes-{uuid.uuid4().hex[:4]}")
        assert mock_clear.called

        mock_clear.reset_mock()
        product.name = "Updated Shoes"
        product.save()
        assert mock_clear.called

        mock_clear.reset_mock()
        product.delete()
        assert mock_clear.called

        mock_clear.reset_mock()
        brand.delete()
        assert mock_clear.called

@pytest.mark.django_db
def test_signals_cache_delete_pattern():
    with patch.object(cache, "delete_pattern", create=True) as mock_delete_pattern:
        Category.objects.create(name="Shirts", slug=f"shirts-{uuid.uuid4().hex[:4]}")
        mock_delete_pattern.assert_called_with("*views.decorators.cache*")