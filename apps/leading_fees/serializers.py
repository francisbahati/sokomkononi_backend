from rest_framework import serializers

from .models import LeadingFeeConfig


class LeadingFeeConfigSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()
    desc = serializers.SerializerMethodField()

    class Meta:
        model = LeadingFeeConfig
        fields = ["id", "price", "days", "label", "desc", "updated_at"]
        read_only_fields = ["id", "updated_at"]

    def get_label(self, obj):
        return {"sw": obj.label_sw, "en": obj.label_en}

    def get_desc(self, obj):
        return {"sw": obj.desc_sw, "en": obj.desc_en}

    def to_internal_value(self, data):
        # Accept both flat + bilingual input
        out = {}
        if "price" in data:
            out["price"] = data["price"]
        if "days" in data:
            out["days"] = data["days"]
        label = data.get("label") or {}
        if isinstance(label, dict):
            if "sw" in label:
                out["label_sw"] = label["sw"]
            if "en" in label:
                out["label_en"] = label["en"]
        if "label_sw" in data:
            out["label_sw"] = data["label_sw"]
        if "label_en" in data:
            out["label_en"] = data["label_en"]
        desc = data.get("desc") or {}
        if isinstance(desc, dict):
            if "sw" in desc:
                out["desc_sw"] = desc["sw"]
            if "en" in desc:
                out["desc_en"] = desc["en"]
        if "desc_sw" in data:
            out["desc_sw"] = data["desc_sw"]
        if "desc_en" in data:
            out["desc_en"] = data["desc_en"]
        return out

    def create(self, validated_data):
        obj, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        for k, v in validated_data.items():
            setattr(obj, k, v)
        obj.save()
        return obj

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        return instance
