# apps/deals/urls.py
"""
User-facing Deal Room routes (mounted at /api/deals/).

Admin routes ziko kwenye `urls_admin.py` (mounted at /api/admin/deals/).

KWA NINI HATUTUMII DefaultRouter:
`DealRoomViewSet` ina actions mbili zenye `url_path` ile ile:
  - "offers"   → GET `offers_list`   na POST `offer`
  - "messages" → GET `messages_list` na POST `messages_create`
Router ingeunda routes mbili zenye URL ile ile; ya kwanza ingeshinda na
nyingine ingerudisha 405. Hivyo tunaunganisha methods kwa kila URL hapa.
"""
from django.urls import path

from .views import DealRoomViewSet


urlpatterns = [
    # ── Deal rooms: list (GET) + create (POST) ──
    path(
        "",
        DealRoomViewSet.as_view({"get": "list", "post": "create"}),
        name="deal-room-list",
    ),

    # ── Detail (GET) ──
    path(
        "<int:pk>/",
        DealRoomViewSet.as_view({"get": "retrieve"}),
        name="deal-room-detail",
    ),

    # ── Offers: list (GET) + send (POST) ──
    path(
        "<int:pk>/offers/",
        DealRoomViewSet.as_view({"get": "offers_list", "post": "offer"}),
        name="deal-room-offers",
    ),
    path(
        "<int:pk>/accept-offer/",
        DealRoomViewSet.as_view({"post": "accept_offer"}),
        name="deal-room-accept-offer",
    ),
    path(
        "<int:pk>/decline-offer/",
        DealRoomViewSet.as_view({"post": "decline_offer"}),
        name="deal-room-decline-offer",
    ),

    # ── Messages: list (GET) + send (POST) ──
    path(
        "<int:pk>/messages/",
        DealRoomViewSet.as_view(
            {"get": "messages_list", "post": "messages_create"}
        ),
        name="deal-room-messages",
    ),

    # ── Payment proof / report ──
    path(
        "<int:pk>/payment-proof/",
        DealRoomViewSet.as_view({"get": "payment_proof"}),
        name="deal-room-payment-proof",
    ),
    path(
        "<int:pk>/report/",
        DealRoomViewSet.as_view({"post": "report"}),
        name="deal-room-report",
    ),

    # ── Cancel / reopen ──
    path(
        "<int:pk>/cancel/",
        DealRoomViewSet.as_view({"post": "cancel"}),
        name="deal-room-cancel",
    ),
    path(
        "<int:pk>/reopen/",
        DealRoomViewSet.as_view({"post": "reopen"}),
        name="deal-room-reopen",
    ),
]