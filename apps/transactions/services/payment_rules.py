# apps/transactions/services/payment_rules.py
"""
Sheria za malipo ya mwisho yanayofanyika NJE ya mfumo (mtindo wa Binance P2P).

- Mnunuzi ana saa 72 kulipa baada ya kuridhika na ukaguzi.
- Muuzaji ana saa 1 kujibu baada ya uthibitisho kupakiwa.
- Mnunuzi anaweza kupakia uthibitisho hadi mara 3.
- Muda ukiisha / majaribio yakiisha => rufaa kwa admin (si kukamilisha yenyewe).
"""
from datetime import timedelta

FINAL_PAYMENT_WINDOW_HOURS = 72
SELLER_RESPONSE_WINDOW_HOURS = 1
MAX_PROOF_ATTEMPTS = 3

DISPUTE_PAYMENT_APPEAL = "PAYMENT_APPEAL"          # mtumiaji alifungua
DISPUTE_PROOF_REJECTED_MAX = "PROOF_REJECTED_MAX"  # majaribio 3 yamekataliwa
DISPUTE_SELLER_NO_RESPONSE = "SELLER_NO_RESPONSE"  # muuzaji alikaa kimya


def final_payment_deadline(now):
    return now + timedelta(hours=FINAL_PAYMENT_WINDOW_HOURS)


def seller_response_deadline(now):
    return now + timedelta(hours=SELLER_RESPONSE_WINDOW_HOURS)


def compute_payment_state(txn, deal_room):
    """
    Nani anasubiriwa sasa? Frontend inatumia hii kuchora lebo ya zamu
    (kijani = zamu yako, kijivu = unasubiri) bila kukisia.

    Rudisha dict:
      awaiting: "buyer" | "seller" | "admin" | "none"
      stage:    msimbo mfupi wa hatua (kwa lebo za UI)
      final_payment_due_at, seller_response_due_at,
      proof_attempts, proof_attempts_left
    """
    from ..models import Transaction  # epuka circular import

    deal_status = getattr(deal_room, "status", "")
    base = {
        "awaiting": "none",
        "stage": "",
        "final_payment_due_at": None,
        "seller_response_due_at": None,
        "proof_attempts": 0,
        "proof_attempts_left": MAX_PROOF_ATTEMPTS,
        "dispute_reason": "",
        "dispute_note": "",
        "dispute_opened_by": "",
        "buyer_decision": "",
        "buyer_decision_note": "",
    }

    if deal_status in ("COMPLETED",):
        base["stage"] = "completed"
        return base
    if deal_status in ("CANCELLED",):
        base["stage"] = "cancelled"
        return base

    if txn is None:
        if deal_status == "ACCEPTED":
            base.update(awaiting="buyer", stage="reservation_due")
        elif deal_status in ("OPEN", "NEGOTIATING"):
            base["stage"] = "negotiating"
        return base

    attempts = txn.proof_attempts or 0
    base.update(
        final_payment_due_at=txn.final_payment_due_at,
        seller_response_due_at=txn.seller_response_due_at,
        proof_attempts=attempts,
        proof_attempts_left=max(0, MAX_PROOF_ATTEMPTS - attempts),
        dispute_reason=txn.dispute_reason or "",
        dispute_note=txn.dispute_note or "",
        dispute_opened_by=(
            "buyer" if txn.dispute_opened_by_id == txn.buyer_id
            else "seller" if txn.dispute_opened_by_id == txn.seller_id
            else "system" if txn.dispute_reason else ""
        ),
        buyer_decision=txn.buyer_decision or "",
        buyer_decision_note=txn.buyer_decision_note or "",
    )

    st = txn.status
    if st == Transaction.Status.DISPUTED:
        base.update(awaiting="admin", stage="disputed")
    elif st == Transaction.Status.READY_FOR_FINAL_PAYMENT:
        if txn.final_payment_uploaded_at:
            base.update(awaiting="seller", stage="proof_submitted")
        else:
            base.update(awaiting="buyer", stage="final_payment_due")
    elif st in (Transaction.Status.INSPECTION, Transaction.Status.RESERVED):
        base.update(awaiting="buyer", stage="inspection")
    elif st in (
        Transaction.Status.RESERVATION_PENDING, Transaction.Status.PENDING,
    ):
        base.update(awaiting="buyer", stage="reservation_due")
    return base
