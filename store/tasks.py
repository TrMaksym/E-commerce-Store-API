from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from celery import shared_task
from django.core.mail import send_mail
from store.models import Order


@shared_task
def send_order_confirmation_email(order_id):
    order = Order.objects.filter(id=order_id).first()
    if not order or not order.contact_email:
        return f"Order #{order_id} not found or no contact email provided"

    subject = f"Order Confirmation for Order #{order_id}"
    message = (
        f"Hi,\n\n"
        f"Thank you for your order. Your order number is #{order_id}\n"
        f"Total price: ${order.total_price}\n"
        f"Status: {order.status}\n\n"
        f"We are preparing your items for delivery."
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[order.contact_email],
        fail_silently=False,
    )
    return f"Confirmation sent for Order #{order.id}"

@shared_task
def cancel_expired_orders():
    cutoff = timezone.now() - timedelta(hours=24)
    expired_orders = Order.objects.filter(
        status=Order.Status.PENDING,
        created_at__lte=cutoff
    ).prefetch_related("items")
    for order in expired_orders:
        with transaction.atomic():
            order.status = Order.Status.CANCELED
            order.save(update_fields=["status"])
            for item in order.items.all():
                item.variant.quantity = F("quantity") + item.quantity
                item.variant.save(update_fields=["quantity"])
    return f"Canceled {len(expired_orders)} expired orders"



