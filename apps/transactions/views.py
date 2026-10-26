# ============================================================
# apps/transactions/views.py
# ============================================================

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction as db_transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.deals.models import DealRoom

from .models import (
    InspectionPeriod,
    Reservation,
    ReservationExtension,
    Transaction,
)
from .serializers import (
    BuyerDecisionSerializer,
    FinalPaymentProofSerializer,
    InspectionPeriodSerializer,
    MyTransactionSerializer,
    ReservationSerializer,
    SellerConfirmPaymentSerializer,
    TransactionCreateSerializer,
    TransactionDetailSerializer,
    TransactionListSerializer,
    TransactionCancelSerializer,
)
from .services.dispute import resolve_dispute
from .services.reservation import (
    confirm_reservation_payment,
    create_reservation,
    expire_inspection_period,
    expire_reservation,
    initiate_reservation_payment,
    start_inspection_period,
    get_allowed_reservation_hours,
    calculate_reservation_fee,
    remove_reservation_by_buyer,
    request_reservation_extension,
    confirm_extension_with_credits,
    initiate_extension_payment,
)
from .services.transaction import (
    cancel_transaction,
    create_transaction_from_deal_room,
    reject_final_payment_proof,
    seller_confirm_final_payment,
    submit_buyer_decision,
    upload_final_payment_proof,
)


# ============================================================================
# PERMISSION
# ============================================================================

def _log(request, action, target="", target_id=None, details=""):
    try:
        from apps.audit.services.audit import log_action
        log_action(request=request, action=action, target=target,
                   target_id=target_id, details=details)
    except Exception:
        import logging; logging.getLogger(__name__).exception("audit failed: %s", action)


class IsVerifiedTransactionUser(permissions.BasePermission):
    message = (
        "Akaunti yako lazima iwe active na imethibitishwa "
        "ili kutumia Transactions."
    )

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_staff:
            return True

        return bool(user.is_active and user.is_verified)


# ============================================================================
# TRANSACTION VIEWSET
# ============================================================================

class TransactionViewSet(viewsets.GenericViewSet):

    http_method_names = ["get", "post", "head", "options"]

    permission_classes = [
        permissions.IsAuthenticated,
        IsVerifiedTransactionUser,
    ]

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    throttle_scope = "user"

    queryset = Transaction.objects.none()

    def get_queryset(self):
        user = self.request.user

        queryset = (
            Transaction.objects
            .select_related("listing", "buyer", "seller", "deal_room")
            .prefetch_related("reservation", "inspection_period")
            .order_by("-created_at")
        )

        if user.is_staff:
            return queryset

        return queryset.filter(Q(buyer=user) | Q(seller=user))

    def get_serializer_class(self):
        if self.action == "create":
            return TransactionCreateSerializer
        if self.action == "list":
            return TransactionListSerializer
        if self.action == "my_transactions":
            return MyTransactionSerializer
        if self.action == "reservation":
            return ReservationSerializer
        if self.action == "inspection":
            return InspectionPeriodSerializer
        if self.action == "decision":
            return BuyerDecisionSerializer
        if self.action == "final_payment":
            return FinalPaymentProofSerializer
        if self.action == "confirm_payment":
            return SellerConfirmPaymentSerializer
        if self.action == "cancel":
            return TransactionCancelSerializer
        return TransactionDetailSerializer

    def list(self, request, *args, **kwargs):
        transactions = self.get_queryset()
        page = self.paginate_queryset(transactions)

        serializer = self.get_serializer(
            page if page is not None else transactions,
            many=True,
            context={"request": request},
        )

        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        transaction = self._get_transaction(pk)

        serializer = TransactionDetailSerializer(
            transaction, context={"request": request},
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        deal_room = serializer.validated_data["deal_room"]

        try:
            transaction = create_transaction_from_deal_room(
                deal_room=deal_room,
                user=request.user,
            )
        except IntegrityError:
            raise ValidationError(
                "Transaction tayari imeundwa kwa Deal Room hii."
            )

        response_serializer = TransactionDetailSerializer(
            transaction, context={"request": request},
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="mine")
    def my_transactions(self, request):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        serializer = MyTransactionSerializer(
            page if page is not None else queryset,
            many=True,
            context={"request": request},
        )

        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reservation")
    def reservation(self, request, pk=None):
        transaction = self._get_transaction(pk)

        duration_hours = request.data.get("duration_hours", 48)

        reservation = create_reservation(
            transaction=transaction,
            user=request.user,
            duration_hours=duration_hours,
        )

        serializer = ReservationSerializer(
            reservation, context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="reservation/pay")
    def reservation_pay(self, request, pk=None):
        transaction = self._get_transaction(pk)

        if (
            not request.user.is_staff
            and request.user.id != transaction.buyer_id
        ):
            raise PermissionDenied(
                "Ni mnunuzi au msimamizi pekee anayeweza "
                "kulipia reservation hii."
            )

        reservation = getattr(transaction, "reservation", None)
        if not reservation:
            raise ValidationError("Transaction hii haina Reservation.")


        if reservation.payment_status == Reservation.PaymentStatus.PAID:
            return Response(
                ReservationSerializer(
                    reservation, context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        payment_reference = (request.data.get("payment_reference") or "").strip()

        if payment_reference:
            reservation = confirm_reservation_payment(
                reservation=reservation,
                payment_reference=payment_reference,
                user=request.user,
            )
            return Response(
                ReservationSerializer(
                    reservation, context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        data = initiate_reservation_payment(
            reservation=reservation,
            user=request.user,
            payment_method=request.data.get("payment_method", "mobile"),
            phone=request.data.get("phone", ""),
        )
        return Response(
            {
                "reservation_id": reservation.id,
                "payment_status": (data.get("payment_status") or "PENDING"),
                "fimipay": data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="inspection")
    def inspection(self, request, pk=None):
        transaction = self._get_transaction(pk)

        duration_hours = request.data.get("duration_hours", 24)

        inspection = start_inspection_period(
            transaction=transaction,
            user=request.user,
            duration_hours=duration_hours,
        )

        serializer = InspectionPeriodSerializer(
            inspection, context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="decision")
    def decision(self, request, pk=None):
        transaction = self._get_transaction(pk)

        serializer = BuyerDecisionSerializer(
            data=request.data,
            context={"request": request, "transaction": transaction},
        )
        serializer.is_valid(raise_exception=True)

        updated_transaction = submit_buyer_decision(
            transaction=transaction,
            buyer=request.user,
            decision=serializer.validated_data["buyer_decision"],
            note=serializer.validated_data.get("buyer_decision_note", ""),
        )

        return Response(
            TransactionDetailSerializer(
                updated_transaction, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="final-payment")
    def final_payment(self, request, pk=None):
        transaction = self._get_transaction(pk)

        serializer = FinalPaymentProofSerializer(
            data=request.data,
            context={"request": request, "transaction": transaction},
        )
        serializer.is_valid(raise_exception=True)

        updated_transaction = upload_final_payment_proof(
            transaction=transaction,
            buyer=request.user,
            proof=serializer.validated_data["final_payment_proof"],
            payment_reference=serializer.validated_data.get(
                "final_payment_reference", "",
            ),
        )

        return Response(
            TransactionDetailSerializer(
                updated_transaction, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="confirm-payment")
    def confirm_payment(self, request, pk=None):
        transaction = self._get_transaction(pk)

        serializer = SellerConfirmPaymentSerializer(
            data=request.data,
            context={"request": request, "transaction": transaction},
        )
        serializer.is_valid(raise_exception=True)

        updated_transaction = seller_confirm_final_payment(
            transaction=transaction,
            seller=request.user,
        )

        return Response(
            TransactionDetailSerializer(
                updated_transaction, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ============================================================
    # REJECT PAYMENT PROOF (seller) — MPYA
    # ============================================================
    @action(detail=True, methods=["post"], url_path="reject-payment-proof")
    def reject_payment_proof(self, request, pk=None):
        """
        Muuzaji anakataa uthibitisho wa malipo (bado hajapokea).
        Inafuta proof ili buyer aweze kupakia tena.

        Body (JSON):
            { "reason": "Si sahihi..." }   # hiari
        """
        transaction = self._get_transaction(pk)

        if request.user.id != transaction.seller_id:
            raise PermissionDenied(
                "Ni muuzaji pekee anayeweza kukataa uthibitisho wa malipo."
            )

        reason = (request.data.get("reason") or "").strip()

        updated_transaction = reject_final_payment_proof(
            transaction=transaction,
            seller=request.user,
            reason=reason,
        )

        _log(
            request,
            action="transaction.payment_proof_rejected",
            target="Transaction",
            target_id=updated_transaction.id,
            details=f"reason={(reason or '')[:200]}",
        )

        return Response(
            TransactionDetailSerializer(
                updated_transaction, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        transaction = self._get_transaction(pk)

        serializer = TransactionCancelSerializer(
            data=request.data,
            context={"request": request, "transaction": transaction},
        )
        serializer.is_valid(raise_exception=True)

        updated_transaction = cancel_transaction(
            transaction=transaction,
            user=request.user,
            reason=serializer.validated_data["cancellation_reason"],
        )

        return Response(
            TransactionDetailSerializer(
                updated_transaction, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="resolve-dispute")
    def resolve_dispute_action(self, request, pk=None):
        transaction = self._get_transaction(pk)

        if not request.user.is_staff:
            raise PermissionDenied(
                "Ni admin pekee anayeweza kutatua mgogoro."
            )

        resolution = request.data.get("resolution")
        note = request.data.get("note", "")

        transaction = resolve_dispute(
            transaction=transaction, admin_user=request.user,
            resolution=resolution, note=note,
        )
        _log(request, "transaction.dispute_resolved", "Transaction",
             transaction.id, f"resolution={resolution} note={(note or '')[:200]}")

        return Response(
            TransactionDetailSerializer(
                transaction, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="expire-reservation")
    def expire_reservation(self, request, pk=None):
        transaction = self._get_transaction(pk)

        if not request.user.is_staff:
            raise PermissionDenied(
                "Ni admin pekee anayeweza ku-expire Reservation manually."
            )

        reservation = getattr(transaction, "reservation", None)
        if not reservation:
            raise ValidationError("Transaction hii haina Reservation.")

        reservation = expire_reservation(reservation=reservation)
        _log(request, "reservation.expired", "Reservation",
             reservation.id, f"Transaction #{transaction.id}")

        return Response(
            ReservationSerializer(
                reservation, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="expire-inspection")
    def expire_inspection(self, request, pk=None):
        transaction = self._get_transaction(pk)

        if not request.user.is_staff:
            raise PermissionDenied(
                "Ni admin pekee anayeweza ku-expire Inspection manually."
            )

        inspection = getattr(transaction, "inspection_period", None)
        if not inspection:
            raise ValidationError("Transaction hii haina Inspection Period.")

        inspection = expire_inspection_period(inspection=inspection)
        _log(request, "inspection.expired", "InspectionPeriod",
             inspection.id, f"Transaction #{transaction.id}")

        return Response(
            InspectionPeriodSerializer(
                inspection, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ============================================================
    # EXTEND RESERVATION (buyer)
    # ============================================================
    @action(detail=True, methods=["post"], url_path="extend-reservation")
    def extend_reservation(self, request, pk=None):
        transaction = self._get_transaction(pk)

        if request.user.id != transaction.buyer_id:
            raise PermissionDenied(
                "Ni mnunuzi pekee anayeweza kuongeza muda wa reservation."
            )

        reservation = getattr(transaction, "reservation", None)
        if not reservation:
            raise ValidationError("Transaction hii haina Reservation.")

        extension = request_reservation_extension(
            reservation=reservation,
            user=request.user,
            additional_hours=request.data.get("additional_hours"),
        )

        payment_reference = (
            request.data.get("payment_reference") or ""
        ).strip()

        if extension.status != extension.Status.PAID:
            if payment_reference == "credits":
                confirm_extension_with_credits(
                    extension=extension, user=request.user,
                )
            elif payment_reference:
                raise ValidationError(
                    "Njia hii ya malipo hairuhusiwi. Tumia credits "
                    "au lipa kupitia FimiPay."
                )
            else:
                data = initiate_extension_payment(
                    extension=extension,
                    user=request.user,
                    payment_method=request.data.get(
                        "payment_method", "mobile",
                    ),
                    phone=request.data.get("phone", ""),
                )
                return Response(
                    {
                        "extension_id": extension.id,
                        "reservation_id": reservation.id,
                        "additional_hours": extension.additional_hours,
                        "fee": str(extension.fee),
                        "payment_status": "PENDING",
                        "fimipay": data,
                    },
                    status=status.HTTP_201_CREATED,
                )

        reservation = Reservation.objects.get(pk=reservation.pk)
        _log(
            request,
            action="reservation.extended",
            target="Reservation",
            target_id=reservation.id,
            details=(
                f"Reservation #{reservation.id} extended by "
                f"{extension.additional_hours}h (fee TZS {extension.fee}) "
                f"for Transaction #{transaction.id}"
            ),
        )

        return Response(
            ReservationSerializer(
                reservation, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ============================================================
    # REMOVE RESERVATION (buyer)
    # ============================================================
    @action(detail=True, methods=["post"], url_path="remove-reservation")
    def remove_reservation(self, request, pk=None):
        transaction = self._get_transaction(pk)

        if request.user.id != transaction.buyer_id:
            raise PermissionDenied(
                "Ni mnunuzi pekee anayeweza kuondoa reservation."
            )

        reservation = getattr(transaction, "reservation", None)
        if not reservation:
            raise ValidationError("Transaction hii haina Reservation.")

        reservation = remove_reservation_by_buyer(reservation=reservation)

        _log(
            request,
            action="reservation.removed_by_buyer",
            target="Reservation",
            target_id=reservation.id,
            details=(
                f"Reservation #{reservation.id} removed by buyer "
                f"for Transaction #{transaction.id}"
            ),
        )

        return Response(
            ReservationSerializer(
                reservation, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ============================================================
    # INTERNAL HELPER
    # ============================================================
    def _get_transaction(self, pk):
        transaction = get_object_or_404(self.get_queryset(), pk=pk)
        user = self.request.user

        if (
            not user.is_staff
            and user.id not in [transaction.buyer_id, transaction.seller_id]
        ):
            raise PermissionDenied(
                "Huruhusiwi kufikia Transaction hii."
            )

        return transaction