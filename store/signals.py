from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from store.models import Category, Brand, Product


@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=Brand)
@receiver([post_save, post_delete], sender=Product)
def invalidate_cache(sender, instance, **kwargs):
    if hasattr(cache, "delete_pattern"):
        cache.delete_pattern("*views.decorators.cache*")
    else:
        cache.clear()
