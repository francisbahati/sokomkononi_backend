from rest_framework import serializers

from .models import AppStoreLinks, PlatformPolicy, Webhook


class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = ["id", "event", "url", "active", "created_at"]
        read_only_fields = ["id", "created_at"]


class AppStoreLinksSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppStoreLinks
        fields = ["play", "appstore", "updated_at"]
        read_only_fields = ["updated_at"]


class PlatformPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformPolicy
        fields = ["listing_lifetime_days", "updated_at"]
        read_only_fields = ["updated_at"]