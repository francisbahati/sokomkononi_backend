from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


# ============================================================
# REGISTER
# ============================================================

class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=150,
        required=True,
    )

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

            if User.objects.filter(email=email).exists():
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
# VERIFY OTP
# ============================================================

class VerifyOTPSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        max_length=254,
    )

    otp_code = serializers.CharField(
        min_length=6,
        max_length=6,
    )

    verification_type = serializers.ChoiceField(
        choices=[
            ("EMAIL", "Email"),
            ("PHONE", "Phone"),
        ]
    )


# ============================================================
# LOGIN
# ============================================================

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        max_length=254,
    )

    password = serializers.CharField(
        write_only=True,
        max_length=128,
    )

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password")

        user = None

        # ----------------------------------------------------
        # EMAIL LOGIN
        # ----------------------------------------------------
        if "@" in identifier:
            user = authenticate(
                username=identifier.lower(),
                password=password,
            )

        # ----------------------------------------------------
        # PHONE LOGIN
        # ----------------------------------------------------
        else:
            try:
                user_obj = User.objects.get(phone=identifier)
            except User.DoesNotExist:
                user_obj = None

            if user_obj and user_obj.check_password(password):
                user = user_obj

        if not user:
            raise serializers.ValidationError(
                "Barua pepe/namba ya simu au nenosiri si sahihi."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "Akaunti yako haipo hai."
            )

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
            "name",
            "email",
            "phone",
            "account_type",
            "date_joined",
            "is_verified",
            "seller_status",
            "buyer_status",
        ]

        read_only_fields = [
            "email",
            "date_joined",
            "is_verified",
            "seller_status",
            "buyer_status",
        ]

    def get_seller_status(self, obj):
        return obj.can_sell

    def get_buyer_status(self, obj):
        return obj.can_buy