from django.urls import path

from .api import create_order_view, order_status_view
from .views import fimipay_webhook


urlpatterns = [
    path("create-order/", create_order_view, name="fimipay-create-order"),
    path("order-status/", order_status_view, name="fimipay-order-status"),
    path("webhook/", fimipay_webhook, name="fimipay-webhook"),
]
