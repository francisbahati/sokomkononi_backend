# ============================================================
# apps/listings/views.py
# ============================================================

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from rest_framework import filters, permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import (
    BusinessDetails,
    EquipmentDetails,
    LandDetails,
    Listing,
    ListingFee,
    ListingImage,
    PropertyDetails,
    VehicleDetails,
)

from .permissions import (
    IsOwnerOrAdmin,
    IsVerifiedUser,
)

from .serializers import (
    AdminPendingListingSerializer,
    BusinessDetailsSerializer,
    EquipmentDetailsSerializer,
    LandDetailsSerializer,
    ListingDetailSerializer,
    ListingFeePaymentSerializer,
    ListingFeeSerializer,
    ListingImageSerializer,
    ListingListSerializer,
    ListingRejectionSerializer,
    ListingWriteSerializer,
    PropertyDetailsSerializer,
    VehicleDetailsSerializer,
)

from .services.listing_fee import create_listing_fee

from .services.listing_moderation import (
    approve_listing,
    reject_listing,
)

from .services.listing_payment import mark_listing_fee_as_paid
from .views_helpers import require_int_listing_id


# ============================================================================
# CATEGORY SLUGS
# ============================================================================

CATEGORY_SLUGS = {
    "property": "nyumba-majengo",
    "land": "viwanja-mashamba",
    "vehicle": "magari",
    "business": "biashara-zinazouzwa",
    "equipment": "mashine-heavy-equipment",
}


# ============================================================================
# LISTING VIEWSET
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Orodha ya matangazo",
        description="Huonyesha matangazo yanayopatikana.",
    ),
    retrieve=extend_schema(
        summary="Angalia tangazo",
        description="Huonyesha taarifa kamili za tangazo.",
    ),
    create=extend_schema(
        summary="Weka tangazo",
        description=(
            "Mtumiaji aliyethibitishwa anaweza kuunda tangazo. "
            "Muuzaji anawekwa moja kwa moja kutoka kwenye akaunti."
        ),
        examples=[
            OpenApiExample(
                "Mfano wa tangazo",
                value={
                    "category_id": 1,
                    "title": "Nyumba nzuri ya vyumba 4 Dar es Salaam",
                    "description": (
                        "Nyumba nzuri yenye vyumba vinne, "
                        "maegesho na huduma muhimu."
                    ),
                    "price": "350000000.00",
                    "location": "Mikocheni, Dar es Salaam",
                },
                request_only=True,
            )
        ],
    ),
    update=extend_schema(summary="Badilisha tangazo"),
    partial_update=extend_schema(summary="Badilisha sehemu ya tangazo"),
    destroy=extend_schema(
        summary="Futa/hifadhi tangazo",
        description=(
            "Tangazo huwekwa kwenye kikapu kwa siku 90. "
            "Muuzaji anaweza kulirejesha kabla ya muda kuisha."
        ),
    ),
)
class ListingViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):

    owner_field = "seller"
    staff_can_restore_any = True

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = [
        "category",
        "status",
        "is_featured",
        "seller",
        "is_boosted",
    ]

    search_fields = [
        "title",
        "description",
        "location",
    ]

    ordering_fields = [
        "created_at",
        "price",
        "views_count",
    ]

    ordering = ["-leading_until", "-created_at"]

    queryset = Listing.objects.select_related(
        "seller",
        "category",
    ).prefetch_related(
        "images",
        "property_details",
        "land_details",
        "vehicle_details",
        "business_details",
        "equipment_details",
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        public_statuses = [
            Listing.Status.AVAILABLE,
            Listing.Status.RESERVED,
            Listing.Status.SOLD,
        ]

        if not user.is_authenticated:
            return queryset.filter(status__in=public_statuses)

        if user.is_staff:
            return queryset

        return queryset.filter(
            Q(status__in=public_statuses) | Q(seller=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return ListingListSerializer

        if self.action == "retrieve":
            return ListingDetailSerializer

        return ListingWriteSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.AllowAny]
        elif self.action == "create":
            permission_classes = [IsVerifiedUser]
        else:
            permission_classes = [IsOwnerOrAdmin]

        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        """
        Override create to return ListingDetailSerializer (with id) instead
        of ListingWriteSerializer (no id). Frontend needs the id to
        upload images, pay fees, etc.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        output = ListingDetailSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save(
            seller=self.request.user,
            status=Listing.Status.DRAFT,
        )

    def perform_update(self, serializer):
        instance = self.get_object()

        if self.request.user.is_staff:
            serializer.save()
            return

        serializer.save(
            seller=instance.seller,
            status=instance.status,
        )

    def destroy(self, request, *args, **kwargs):
        listing = self.get_object()

        if request.user.is_staff and request.query_params.get(
            "hard", "false"
        ).lower() in ("true", "1", "yes"):
            listing.hard_delete()
            return Response(
                {"detail": "Tangazo limefutwa kabisa."},
                status=status.HTTP_204_NO_CONTENT,
            )

        listing.delete(
            by=request.user,
            reason=request.data.get("reason", "") if isinstance(
                request.data, dict
            ) else "",
        )

        return Response(
            {
                "detail": (
                    "Tangazo limewekwa kwenye kikapu. "
                    "Litaondolewa kabisa baada ya siku 90."
                )
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# REUSABLE CATEGORY DETAILS VIEWSET
# ============================================================================

class CategoryDetailsViewSet(viewsets.ModelViewSet):

    lookup_url_kwarg = "listing_id"

    detail_model = None
    detail_serializer = None
    required_category_slug = None
    already_exists_message = "Maelezo tayari yapo."
    created_message = "Maelezo yameongezwa."
    deleted_message = "Maelezo yamefutwa."

    # Placeholder for drf-spectacular. Real data comes from get_queryset().
    queryset = PropertyDetails.objects.none()

    def get_serializer_class(self):
        return self.detail_serializer

    def get_queryset(self):
        # drf-spectacular calls get_queryset() during schema generation
        # without URL kwargs. Return an empty queryset in that case.
        if getattr(self, "swagger_fake_view", False):
            if self.detail_model is not None:
                return self.detail_model.objects.none()
            return PropertyDetails.objects.none()

        listing = self.get_listing()
        return self.detail_model.objects.filter(listing=listing)

    def get_permissions(self):
        if self.action == "retrieve":
            return [permissions.AllowAny()]
        return [IsVerifiedUser(), IsOwnerOrAdmin()]

    def get_listing(self):
        return get_object_or_404(
            Listing.objects.select_related("seller", "category"),
            pk=self.kwargs[self.lookup_url_kwarg],
        )

    def check_owner(self, listing):
        if self.request.user.is_staff:
            return True
        return listing.seller_id == self.request.user.id

    def validate_listing_category(self, listing):
        if listing.category.slug != self.required_category_slug:
            return Response(
                {
                    "detail": (
                        f"Tangazo hili si la kundi "
                        f"{self.required_category_slug}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def create(self, request, *args, **kwargs):
        listing = self.get_listing()

        if not self.check_owner(listing):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kubadilisha "
                        "taarifa za tangazo ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        category_error = self.validate_listing_category(listing)
        if category_error:
            return category_error

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                if self.detail_model.objects.filter(
                    listing=listing,
                ).exists():
                    raise IntegrityError("already_exists")
                serializer.save(listing=listing)
        except IntegrityError:
            return Response(
                {"detail": self.already_exists_message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        listing = self.get_listing()

        if not request.user.is_authenticated:
            if listing.status not in [
                Listing.Status.AVAILABLE,
                Listing.Status.RESERVED,
                Listing.Status.SOLD,
            ]:
                return Response(
                    {"detail": "Tangazo halipatikani."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif not (
            request.user.is_staff
            or listing.seller_id == request.user.id
            or listing.status in [
                Listing.Status.AVAILABLE,
                Listing.Status.RESERVED,
                Listing.Status.SOLD,
            ]
        ):
            return Response(
                {"detail": "Tangazo halipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        obj = get_object_or_404(self.detail_model, listing=listing)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        return self._update_details(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update_details(request, partial=True)

    def _update_details(self, request, partial):
        listing = self.get_listing()

        if not self.check_owner(listing):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kubadilisha "
                        "taarifa za tangazo ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        obj = get_object_or_404(self.detail_model, listing=listing)

        serializer = self.get_serializer(
            obj, data=request.data, partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        listing = self.get_listing()

        if not self.check_owner(listing):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kufuta taarifa hizi."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        obj = get_object_or_404(self.detail_model, listing=listing)
        obj.delete()

        return Response(
            {"detail": self.deleted_message},
            status=status.HTTP_200_OK,
        )


# ============================================================================
# PROPERTY
# ============================================================================

class PropertyDetailsViewSet(CategoryDetailsViewSet):
    detail_model = PropertyDetails
    detail_serializer = PropertyDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["property"]
    queryset = PropertyDetails.objects.none()

    already_exists_message = (
        "Maelezo ya nyumba/jengo tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya nyumba/jengo yamefutwa."


# ============================================================================
# LAND
# ============================================================================

class LandDetailsViewSet(CategoryDetailsViewSet):
    detail_model = LandDetails
    detail_serializer = LandDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["land"]
    queryset = LandDetails.objects.none()

    already_exists_message = (
        "Maelezo ya ardhi tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya ardhi yamefutwa."


# ============================================================================
# VEHICLE
# ============================================================================

class VehicleDetailsViewSet(CategoryDetailsViewSet):
    detail_model = VehicleDetails
    detail_serializer = VehicleDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["vehicle"]
    queryset = VehicleDetails.objects.none()

    already_exists_message = (
        "Maelezo ya gari tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya gari yamefutwa."


# ============================================================================
# BUSINESS
# ============================================================================

class BusinessDetailsViewSet(CategoryDetailsViewSet):
    detail_model = BusinessDetails
    detail_serializer = BusinessDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["business"]
    queryset = BusinessDetails.objects.none()

    already_exists_message = (
        "Maelezo ya biashara tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya biashara yamefutwa."


# ============================================================================
# EQUIPMENT
# ============================================================================

class EquipmentDetailsViewSet(CategoryDetailsViewSet):
    detail_model = EquipmentDetails
    detail_serializer = EquipmentDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["equipment"]
    queryset = EquipmentDetails.objects.none()

    already_exists_message = (
        "Maelezo ya mashine tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya mashine yamefutwa."


# ============================================================================
# LISTING IMAGE VIEWSET
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Orodha ya picha za tangazo",
        description="Huonyesha picha zote za tangazo kwa mpangilio.",
    ),
    retrieve=extend_schema(summary="Angalia picha ya tangazo"),
    create=extend_schema(
        summary="Ongeza picha kwenye tangazo",
        description=(
            "Muuzaji anaweza kuongeza picha kwenye tangazo lake. "
            "Admin anaweza kuongeza picha kwenye tangazo lolote."
        ),
        request={"multipart/form-data": ListingImageSerializer},
        responses={
            201: ListingImageSerializer,
            400: OpenApiResponse(description="Taarifa za picha si sahihi."),
            403: OpenApiResponse(description="Huna ruhusa ya kuongeza picha."),
        },
    ),
    partial_update=extend_schema(
        summary="Badilisha taarifa za picha",
        description="Badilisha picha kuwa primary au badilisha mpangilio wake.",
    ),
    destroy=extend_schema(summary="Futa picha ya tangazo"),
)
class ListingImageViewSet(viewsets.ModelViewSet):

    serializer_class = ListingImageSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    # Placeholder for drf-spectacular.
    queryset = ListingImage.objects.none()

    def get_queryset(self):
        # drf-spectacular calls get_queryset() without URL kwargs.
        if getattr(self, "swagger_fake_view", False):
            return ListingImage.objects.none()

        listing_id = self.kwargs.get("listing_id")
        listing = get_object_or_404(Listing, pk=listing_id)
        user = self.request.user

        if user.is_authenticated and user.is_staff:
            return ListingImage.objects.filter(listing=listing).order_by(
                "ordering", "created_at",
            )

        if user.is_authenticated and listing.seller_id == user.id:
            return ListingImage.objects.filter(listing=listing).order_by(
                "ordering", "created_at",
            )

        if listing.status in [
            Listing.Status.AVAILABLE,
            Listing.Status.RESERVED,
            Listing.Status.SOLD,
        ]:
            return ListingImage.objects.filter(listing=listing).order_by(
                "ordering", "created_at",
            )

        return ListingImage.objects.none()

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsVerifiedUser, IsOwnerOrAdmin]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        listing_id, err = require_int_listing_id(kwargs.get("listing_id"))
        if err:
            return err
        listing = get_object_or_404(Listing, pk=listing_id)

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kuongeza picha kwenye "
                        "tangazo ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        image = request.FILES.get("image")
        if not image:
            return Response(
                {"detail": "Picha inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if image.content_type not in allowed_types:
            return Response(
                {
                    "detail": (
                        "Aina ya picha hairuhusiwi. "
                        "Tumia JPG, PNG au WEBP."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            return Response(
                {"detail": "Picha haiwezi kuzidi ukubwa wa 5 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_primary = request.data.get("is_primary", False)
        if isinstance(is_primary, str):
            is_primary = is_primary.lower() in ["true", "1", "yes"]

        try:
            ordering = int(request.data.get("ordering", 0))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Ordering lazima iwe namba."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ordering < 0:
            return Response(
                {"detail": "Ordering haiwezi kuwa chini ya sifuri."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            has_images = ListingImage.objects.filter(
                listing=listing,
            ).exists()

            if not has_images:
                is_primary = True

            if is_primary:
                ListingImage.objects.filter(
                    listing=listing, is_primary=True,
                ).update(is_primary=False)

            image_object = ListingImage.objects.create(
                listing=listing,
                image=image,
                is_primary=is_primary,
                ordering=ordering,
            )

        return Response(
            self.get_serializer(image_object).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        image_object = self.get_object()
        listing = image_object.listing

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kubadilisha picha ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        is_primary = request.data.get("is_primary", None)
        ordering = request.data.get("ordering", None)

        if ordering is not None:
            try:
                ordering = int(ordering)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Ordering lazima iwe namba."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ordering < 0:
                return Response(
                    {"detail": "Ordering haiwezi kuwa chini ya sifuri."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            if is_primary is not None:
                if isinstance(is_primary, str):
                    is_primary = is_primary.lower() in ["true", "1", "yes"]

                if is_primary:
                    ListingImage.objects.filter(
                        listing=listing, is_primary=True,
                    ).exclude(pk=image_object.pk).update(is_primary=False)
                    image_object.is_primary = True
                else:
                    if image_object.is_primary:
                        other_primary_exists = (
                            ListingImage.objects
                            .filter(listing=listing, is_primary=True)
                            .exclude(pk=image_object.pk)
                            .exists()
                        )
                        if not other_primary_exists:
                            return Response(
                                {
                                    "detail": (
                                        "Tangazo lazima liwe na "
                                        "angalau picha moja kuu."
                                    )
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        image_object.is_primary = False

            if ordering is not None:
                image_object.ordering = ordering

            image_object.save()

        return Response(
            self.get_serializer(image_object).data,
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        image_object = self.get_object()
        listing = image_object.listing

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kufuta picha ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        was_primary = image_object.is_primary

        with transaction.atomic():
            image_object.delete()

            if was_primary:
                next_image = (
                    ListingImage.objects
                    .filter(listing=listing)
                    .order_by("ordering", "created_at")
                    .first()
                )
                if next_image:
                    ListingImage.objects.filter(
                        listing=listing,
                    ).update(is_primary=False)
                    next_image.is_primary = True
                    next_image.save(update_fields=["is_primary"])

        return Response(
            {"detail": "Picha imefutwa."},
            status=status.HTTP_200_OK,
        )


# ============================================================================
# LISTING FEE API
# ============================================================================

@extend_schema(
    summary="Angalia ada ya tangazo",
    description=(
        "Hupata ada ya tangazo iliyotengenezwa. Kama haijatengenezwa, "
        "tumia endpoint ya payment ili kuitengeneza."
    ),
    responses={
        200: ListingFeeSerializer,
        403: OpenApiResponse(description="Huna ruhusa ya kuona ada hii."),
        404: OpenApiResponse(
            description="Tangazo au ada haijapatikana."
        ),
    },
)
class ListingFeeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, listing_id):
        listing_id, err = require_int_listing_id(listing_id)
        if err:
            return err
        listing = get_object_or_404(Listing, id=listing_id)

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {"detail": "Huna ruhusa ya kuona ada ya tangazo hili."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            listing_fee = ListingFee.objects.get(listing=listing)
        except ListingFee.DoesNotExist:
            return Response(
                {"detail": "Ada ya tangazo haijatengenezwa bado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            ListingFeeSerializer(
                listing_fee, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


# ============================================================================
# LISTING FEE PAYMENT API
# ============================================================================

@extend_schema(
    summary="Lipa ada ya tangazo",
    description=(
        "Huthibitisha malipo ya ada ya tangazo. "
        "Kwa sasa endpoint hii ni simulation ya payment service. "
        "Baadaye itaunganishwa na payment gateway/webhook."
    ),
    request=ListingFeePaymentSerializer,
    responses={
        200: ListingFeeSerializer,
        400: OpenApiResponse(description="Malipo hayawezi kukamilishwa."),
        403: OpenApiResponse(description="Huna ruhusa ya kulipia tangazo hili."),
        404: OpenApiResponse(description="Tangazo au ada haijapatikana."),
    },
)
class ListingFeePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, listing_id):
        listing_id, err = require_int_listing_id(listing_id)
        if err:
            return err
        listing = get_object_or_404(Listing, id=listing_id)

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {"detail": "Huna ruhusa ya kulipia ada ya tangazo hili."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ListingFeePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        create_listing_fee(listing)

        try:
            listing_fee = mark_listing_fee_as_paid(
                listing,
                serializer.validated_data["payment_reference"],
            )
        except ListingFee.DoesNotExist:
            return Response(
                {"detail": "Ada ya tangazo haijapatikana."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as exc:
            detail = getattr(exc, "detail", str(exc))
            return Response(
                {"detail": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ListingFeeSerializer(
                listing_fee, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


# ============================================================================
# ADMIN LISTING MODERATION
# ============================================================================

@extend_schema(
    summary="Orodha ya matangazo yanayosubiri idhini",
    description=(
        "Huonyesha matangazo yote yenye hali ya "
        "PENDING_APPROVAL kwa wasimamizi wa mfumo pekee."
    ),
    responses={
        200: AdminPendingListingSerializer(many=True),
        403: OpenApiResponse(
            description=(
                "Ni wasimamizi wa mfumo pekee wanaoweza "
                "kuona matangazo yanayosubiri idhini."
            )
        ),
    },
)

class AdminPendingListingsView(GenericAPIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        listings = (
            Listing.objects
            .filter(status=Listing.Status.PENDING_APPROVAL)
            .select_related("seller", "category", "listing_fee")
            .prefetch_related("images")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(listings)
        serializer = AdminPendingListingSerializer(
            page if page is not None else listings,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response(
            {"count": listings.count(), "results": serializer.data},
            status=status.HTTP_200_OK,
        )


# ============================================================================
# ADMIN APPROVE LISTING
# ============================================================================

@extend_schema(
    summary="Idhinisha tangazo",
    description=(
        "Humruhusu admin kuidhinisha tangazo lililo kwenye "
        "PENDING_APPROVAL. Ada ya tangazo lazima iwe imelipwa "
        "kabla ya tangazo kuidhinishwa."
    ),
    responses={
        200: ListingDetailSerializer,
        400: OpenApiResponse(description="Tangazo haliwezi kuidhinishwa."),
        403: OpenApiResponse(description="Ni admin pekee."),
        404: OpenApiResponse(description="Tangazo halijapatikana."),
    },
)
class AdminApproveListingView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, listing_id):
        try:
            listing = approve_listing(
                listing_id=listing_id,
                admin_user=request.user,
            )
        except Listing.DoesNotExist:
            return Response(
                {"detail": "Tangazo halijapatikana."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as exc:
            detail = getattr(exc, "detail", str(exc))
            return Response(
                {"detail": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ListingDetailSerializer(
            listing, context={"request": request},
        )

        return Response(
            {
                "detail": "Tangazo limeidhinishwa na sasa linapatikana.",
                "listing": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# ADMIN REJECT LISTING
# ============================================================================

@extend_schema(
    summary="Kataa tangazo",
    description=(
        "Humruhusu admin kukataa tangazo lililo kwenye "
        "PENDING_APPROVAL. Sababu ya kukataa inahitajika."
    ),
    request=ListingRejectionSerializer,
    responses={
        200: ListingDetailSerializer,
        400: OpenApiResponse(description="Sababu haijawekwa."),
        403: OpenApiResponse(description="Ni admin pekee."),
        404: OpenApiResponse(description="Tangazo halijapatikana."),
    },
)
class AdminRejectListingView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, listing_id):
        serializer = ListingRejectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            listing = reject_listing(
                listing_id=listing_id,
                admin_user=request.user,
                rejection_reason=serializer.validated_data[
                    "rejection_reason"
                ],
            )
        except Listing.DoesNotExist:
            return Response(
                {"detail": "Tangazo halijapatikana."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as exc:
            detail = getattr(exc, "detail", str(exc))
            return Response(
                {"detail": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = ListingDetailSerializer(
            listing, context={"request": request},
        )

        return Response(
            {
                "detail": "Tangazo limekataliwa.",
                "listing": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )