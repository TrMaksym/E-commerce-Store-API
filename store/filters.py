from django_filters import rest_framework as filters
from store.models import Product


class ProductFilter(filters.FilterSet):
  min_price = filters.NumberFilter(
      field_name="variants__price", lookup_expr="gte", distinct=True
  )
  max_price = filters.NumberFilter(
      field_name="variants__price", lookup_expr="lte", distinct=True
  )
  category = filters.NumberFilter(field_name="category")
  brand = filters.NumberFilter(field_name="brand")
  in_stock = filters.BooleanFilter(method="filter_in_stock")

  class Meta:
    model = Product
    fields = ["category", "brand", "in_stock", "min_price", "max_price"]

  @staticmethod
  def filter_in_stock(queryset, name, value):
    if value is True:
      return queryset.filter(variants__quantity__gt=0).distinct()
    if value is False:
      return queryset.filter(variants__quantity=0).distinct()
    return queryset