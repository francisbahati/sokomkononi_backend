# apps/deals/services/system_messages.py
import logging

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.deals.models import DealMessage, DealRoom

logger = logging.getLogger(__name__)

# Maandishi ya akiba (admin, transcript, clients za zamani).
# UI ya mtumiaji inatafsiri kwa `system_code`.
FALLBACK_TEXT = {
    "RESERVATION_PAID": "Reservation imelipwa. / Reservation paid.",
    "INSPECTION_PASSED": "Ukaguzi umepita. / Inspection passed.",
    "PROOF_SUBMITTED": "Uthibitisho wa malipo umetumwa. / Payment proof submitted.",
    "PROOF_REJECTED": "Muuzaji bado hajapokea malipo. / Seller has not received payment.",
    "COMPLETED": "Muamala umekamilika. / Transaction completed.",
    "DISPUTED": "Mgogoro umeripotiwa. / A dispute has been reported.",
    "INSPECTION_CANCELLED": "Mnunuzi ameghairi baada ya ukaguzi. / Buyer cancelled after inspection.",
}


def post_system_message(*, deal_room_id, code, actor, data=None):
    """
    Andika ujumbe wa SYSTEM baada ya commit, ili kushindwa kwake
    kusirudishe nyuma malipo/hatua. Idempotent kwa `data["key"]`.
    `data` lazima iwe JSON-safe (Decimal/tarehe → str).
    """
    data = dict(data or {})
    key = data.get("key")

    def _run():
        try:
            if key and DealMessage.objects.filter(
                deal_room_id=deal_room_id,
                kind=DealMessage.Kind.SYSTEM,
                system_code=code,
                system_data__key=key,
            ).exists():
                return
            DealMessage.objects.create(
                deal_room_id=deal_room_id,
                sender=actor,
                kind=DealMessage.Kind.SYSTEM,
                system_code=code,
                system_data=data,
                text=FALLBACK_TEXT.get(code, ""),
            )
            DealRoom.objects.filter(pk=deal_room_id).update(
                updated_at=timezone.now()
            )
        except Exception:
            logger.exception("system message failed: %s room=%s", code, deal_room_id)

    db_transaction.on_commit(_run)