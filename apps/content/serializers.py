from rest_framework import serializers

from .models import Banner, FAQ, SiteContent, Testimonial


class SiteContentSerializer(serializers.ModelSerializer):
    heading = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()

    heading_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    heading_en = serializers.CharField(required=False, allow_blank=True, write_only=True)
    content_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    content_en = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = SiteContent
        fields = [
            "id", "key", "heading", "content", "extra", "updated_at",
            "heading_sw", "heading_en", "content_sw", "content_en",
        ]
        read_only_fields = ["id", "key", "updated_at"]

    def get_heading(self, obj):
        return {"sw": obj.heading_sw, "en": obj.heading_en}

    def get_content(self, obj):
        return {"sw": obj.content_sw, "en": obj.content_en}

    def to_internal_value(self, data):
        data = dict(data)
        for key in ("heading", "content"):
            val = data.pop(key, None)
            if isinstance(val, dict):
                if "sw" in val:
                    data[f"{key}_sw"] = val["sw"]
                if "en" in val:
                    data[f"{key}_en"] = val["en"]
        return super().to_internal_value(data)


class BannerSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    subtitle = serializers.SerializerMethodField()
    ctaText = serializers.SerializerMethodField()

    title_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    title_en = serializers.CharField(required=False, allow_blank=True, write_only=True)
    subtitle_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    subtitle_en = serializers.CharField(required=False, allow_blank=True, write_only=True)
    cta_text_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    cta_text_en = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Banner
        fields = [
            "id", "title", "subtitle", "ctaText",
            "cta_link", "image_url", "active", "order", "created_at",
            "title_sw", "title_en", "subtitle_sw", "subtitle_en",
            "cta_text_sw", "cta_text_en",
        ]
        read_only_fields = ["id", "created_at"]

    def get_title(self, obj):
        return {"sw": obj.title_sw, "en": obj.title_en}

    def get_subtitle(self, obj):
        return {"sw": obj.subtitle_sw, "en": obj.subtitle_en}

    def get_ctaText(self, obj):
        return {"sw": obj.cta_text_sw, "en": obj.cta_text_en}

    def to_internal_value(self, data):
        data = dict(data)
        pairs = [
            ("title", "title"),
            ("subtitle", "subtitle"),
            ("ctaText", "cta_text"),
        ]
        for src, prefix in pairs:
            val = data.pop(src, None)
            if isinstance(val, dict):
                if "sw" in val:
                    data[f"{prefix}_sw"] = val["sw"]
                if "en" in val:
                    data[f"{prefix}_en"] = val["en"]
        return super().to_internal_value(data)


class TestimonialSerializer(serializers.ModelSerializer):
    quote = serializers.SerializerMethodField()
    quote_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    quote_en = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Testimonial
        fields = [
            "id", "name", "quote", "avatar_url", "rating",
            "active", "created_at", "quote_sw", "quote_en",
        ]
        read_only_fields = ["id", "created_at"]

    def get_quote(self, obj):
        return {"sw": obj.quote_sw, "en": obj.quote_en}

    def to_internal_value(self, data):
        data = dict(data)
        val = data.pop("quote", None)
        if isinstance(val, dict):
            if "sw" in val:
                data["quote_sw"] = val["sw"]
            if "en" in val:
                data["quote_en"] = val["en"]
        return super().to_internal_value(data)


class FAQSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()
    answer = serializers.SerializerMethodField()

    question_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    question_en = serializers.CharField(required=False, allow_blank=True, write_only=True)
    answer_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    answer_en = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = FAQ
        fields = [
            "id", "question", "answer", "active", "order", "created_at",
            "question_sw", "question_en", "answer_sw", "answer_en",
        ]
        read_only_fields = ["id", "created_at"]

    def get_question(self, obj):
        return {"sw": obj.question_sw, "en": obj.question_en}

    def get_answer(self, obj):
        return {"sw": obj.answer_sw, "en": obj.answer_en}

    def to_internal_value(self, data):
        data = dict(data)
        for src, prefix in [("question", "question"), ("answer", "answer")]:
            val = data.pop(src, None)
            if isinstance(val, dict):
                if "sw" in val:
                    data[f"{prefix}_sw"] = val["sw"]
                if "en" in val:
                    data[f"{prefix}_en"] = val["en"]
        return super().to_internal_value(data)
