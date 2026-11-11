# apps/push/urls.py
from django.urls import path

from .views import PushSubscribeView, PushUnsubscribeView


urlpatterns = [
    path("subscribe/", PushSubscribeView.as_view(), name="push-subscribe"),
    path("unsubscribe/", PushUnsubscribeView.as_view(), name="push-unsubscribe"),
]