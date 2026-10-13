import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from store.models import Order, Payment
from store.tasks import send_order_confirmation_email

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    @staticmethod
    def create_checkout_session(order: Order, success_url: str, cancel_url: str) -> stripe.checkout.Session:
        line_items = []
        for item in order.items.all():
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": item.product.title,
                    },
                    "unit_amount": int(item.price * 100),
                },
                "quantity": item.quantity,
            })

        if not line_items:
            raise ValidationError("Cannot create checkout session for an empty order.")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "order_id": str(order.id),
            },
        )
        return session

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret,
        )

    @classmethod
    def handle_checkout_completed(cls, session: dict) -> None:
        order_id = session.get("metadata", {}).get("order_id")
        if not order_id:
            return

        order = Order.objects.filter(id=order_id).first()
        if not order or order.status == Order.Status.PAID:
            return

        with transaction.atomic():
            order.status = Order.Status.PAID
            order.save(update_fields=["status"])

            if order.coupon:
                order.coupon.times_used = F("times_used") + 1
                order.coupon.save(update_fields=["times_used"])

            payment = Payment.objects.filter(transaction_id=session.get("id")).first()
            if payment:
                payment.status = Payment.Status.PAID
                payment.save(update_fields=["status"])

            transaction.on_commit(lambda: send_order_confirmation_email.delay(order.id))