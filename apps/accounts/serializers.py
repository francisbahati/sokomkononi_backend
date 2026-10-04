from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User
from .services import normalize_tanzania_phone


def _validate_otp_digits(value):
    value = (value or "").strip()
    if not value.isdigit() or len(value) != 6:
        raise serializers.ValidationError("OTP lazima iwe namba sita.")
    return value


def _run_password_validators(value):
    try:
        validate_password(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))
    return value


# ============================================================
# REGISTER
# ============================================================

class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)

    email = serializers.EmailField()

    # Contact info only: optional and unique. Never used for OTP or login.
    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    account_type = serializers.ChoiceField(
        choices=User.AccountType.choices,
        default=User.AccountType.INDIVIDUAL,
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
    )

    def validate_email(self, value):
        value = value.strip().lower()
        if User.all_objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Barua pepe hii tayari imesajiliwa."
            )
        return value

    def validate_phone(self, value):
        value = (value or "").strip()
        if not value:
            return None  # store NULL, never ""
        value = normalize_tanzania_phone(value)
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "Namba hii ya simu tayari imesajiliwa."
            )
        return value

    def validate_password(self, value):
        return _run_password_validators(value)


# ============================================================
# VERIFY OTP (registration)
# ============================================================

class VerifyOTPSerializer(serializers.Serializer):
    identifier = serializers.EmailField()
    otp_code = serializers.CharField(min_length=6, max_length=6)

    def validate_identifier(self, value):
        return value.strip().lower()

    def validate_otp_code(self, value):
        return _validate_otp_digits(value)


# ============================================================
# LOGIN
# ============================================================

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip().lower()
        password = attrs.get("password")

        user = User.objects.filter(email=identifier).first()

        if not user or not user.check_password(password):
            raise serializers.ValidationError(
                "Barua pepe au nenosiri si sahihi."
            )

        if not user.is_active:
            raise serializers.ValidationError("Akaunti yako haipo hai.")

        if not user.is_verified:
            raise serializers.ValidationError(
                "Akaunti yako haijathibitishwa."
            )

        attrs["user"] = user
        return attrs


# ============================================================
# PROFILE
# ============================================================

class ProfileSerializer(serializers.ModelSerializer):
    seller_status = serializers.SerializerMethodField()
    buyer_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "name", "email", "phone", "account_type",
            "avatar", "date_joined", "is_verified", "is_staff",
            "is_superuser", "seller_status", "buyer_status",
        ]
        read_only_fields = [
            "id", "email", "date_joined", "is_verified",
            "is_staff", "is_superuser", "seller_status", "buyer_status",
            "avatar",
        ]

    def validate_phone(self, value):
        value = (value or "").strip()
        if not value:
            return None
        value = normalize_tanzania_phone(value)
        qs = User.objects.filter(phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Namba hii ya simu tayari imesajiliwa."
            )
        return value

    def get_seller_status(self, obj):
        return obj.can_sell

    def get_buyer_status(self, obj):
        return obj.can_buy


# ============================================================
# FORGOT PASSWORD — step 1
# ============================================================

class ForgotPasswordSerializer(serializers.Serializer):
    identifier = serializers.EmailField(
        help_text="Barua pepe iliyosajiliwa.",
    )

    def validate_identifier(self, value):
        return value.strip().lower()


# ============================================================
# FORGOT PASSWORD — step 2
# ============================================================

class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    identifier = serializers.EmailField()
    otp_code = serializers.CharField(min_length=6, max_length=6)

    def validate_identifier(self, value):
        return value.strip().lower()

    def validate_otp_code(self, value):
        return _validate_otp_digits(value)


# ============================================================
# FORGOT PASSWORD — step 3
# ============================================================

class PasswordResetSerializer(serializers.Serializer):
    reset_token = serializers.CharField()

    new_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128,
    )

    confirm_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Manenosiri hayafanani."
            })
        return attrs

    def validate_new_password(self, value):
        return _run_password_validators(value)


# ============================================================
# CHANGE PASSWORD (logged-in user)
# ============================================================

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True, max_length=128,
    )

    new_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128,
    )

    confirm_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128,
    )

    def validate_current_password(self, value):
        user = self.context.get("request").user
        if not user.check_password(value):
            raise serializers.ValidationError("Nenosiri la sasa si sahihi.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Manenosiri hayafanani."
            })
        return attrs

    def validate_new_password(self, value):
        return _run_password_validators(value)