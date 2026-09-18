from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


# ============================================================
# REGISTER
# ============================================================

class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=True)

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

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

    def validate(self, attrs):
        email = attrs.get("email")
        phone = attrs.get("phone")

        if not email and not phone:
            raise serializers.ValidationError(
                "Barua pepe au namba ya simu inahitajika."
            )

        if email:
            email = email.strip().lower()
            attrs["email"] = email

            if User.all_objects.filter(email=email).exists():
                raise serializers.ValidationError({
                    "email": "Barua pepe hii tayari imesajiliwa."
                })

        if phone:
            phone = phone.strip()
            attrs["phone"] = phone

            if User.objects.filter(phone=phone).exists():
                raise serializers.ValidationError({
                    "phone": "Namba hii ya simu tayari imesajiliwa."
                })

        return attrs


# ============================================================
# VERIFY OTP (registration)
# ============================================================

class VerifyOTPSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)

    otp_code = serializers.CharField(min_length=6, max_length=6)

    verification_type = serializers.ChoiceField(
        choices=[("EMAIL", "Email"), ("PHONE", "Phone")]
    )

    def validate_otp_code(self, value):
        value = (value or "").strip()
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("OTP lazima iwe namba sita.")
        return value


# ============================================================
# LOGIN
# ============================================================

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)

    password = serializers.CharField(write_only=True, max_length=128)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password")

        user = None

        # Email path uses Django's authenticate(); phone path
        # checks the password directly because USERNAME_FIELD is email.
        if "@" in identifier:
            user = authenticate(
                username=identifier.lower(),
                password=password,
            )
        else:
            user_obj = User.objects.filter(phone=identifier).first()
            if user_obj and user_obj.check_password(password):
                user = user_obj

        if not user:
            raise serializers.ValidationError(
                "Barua pepe/namba ya simu au nenosiri si sahihi."
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
            "date_joined", "is_verified", "is_staff", "is_superuser",
            "seller_status", "buyer_status",
        ]
        read_only_fields = [
            "id", "email", "date_joined", "is_verified",
            "is_staff", "is_superuser", "seller_status", "buyer_status",
        ]

    def get_seller_status(self, obj):
        return obj.can_sell

    def get_buyer_status(self, obj):
        return obj.can_buy


# ============================================================
# FORGOT PASSWORD — step 1
# ============================================================

class ForgotPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        max_length=254,
        required=True,
        help_text="Barua pepe au namba ya simu iliyosajiliwa.",
    )

    def validate_identifier(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError(
                "Barua pepe au namba ya simu inahitajika."
            )
        return value


# ============================================================
# FORGOT PASSWORD — step 2
# ============================================================

class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, required=True)

    otp_code = serializers.CharField(min_length=6, max_length=6, required=True)

    verification_type = serializers.ChoiceField(
        choices=[("EMAIL", "Email"), ("PHONE", "Phone")],
        required=True,
    )

    def validate_identifier(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError(
                "Barua pepe au namba ya simu inahitajika."
            )
        return value

    def validate_otp_code(self, value):
        value = (value or "").strip()
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("OTP lazima iwe namba sita.")
        return value


# ============================================================
# FORGOT PASSWORD — step 3
# ============================================================

class PasswordResetSerializer(serializers.Serializer):
    reset_token = serializers.CharField(required=True)

    new_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, required=True,
    )

    confirm_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, required=True,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Manenosiri hayafanani."
            })
        return attrs

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


# ============================================================
# CHANGE PASSWORD (logged-in user)
# ============================================================

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True, required=True, max_length=128,
    )

    new_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, required=True,
    )

    confirm_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, required=True,
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
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value