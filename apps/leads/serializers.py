from rest_framework import serializers

from .models import Lead


class LeadListingSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    price = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True,
    )
    location = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)


class LeadSerializer(serializers.ModelSerializer):
    listing = LeadListingSerializer(read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "listing",
            "seller",
            "buyer",
            "buyer_name",
            "message",
            "source",
            "status",
            "message_count",
            "deal_room",
            "responded_at",
            "converted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LeadStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Lead.Status.choices)