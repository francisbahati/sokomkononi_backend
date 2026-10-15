# apps/content/serializers.py

from rest_framework import serializers

from .models import Banner, FAQ, SiteContent, Testimonial


class SiteContentSerializer(serializers.ModelSerializer):
    """
    Serializer ya SiteContent (About, Terms, Privacy, Help).

    Inashughulikia:
    - heading (SW/EN) → heading_sw / heading_en
    - content (SW/EN) → content_sw / content_en
    - extra JSON field → subtext, mission, vision, values, team,
      subtitle, sections
    """

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

    def to_representation(self, instance):
        """
        Ongeza fields zilizo kwenye `extra` kwenye response:
        subtext, mission, vision, values, team, subtitle, sections, lastUpdated.
        """
        rep = super().to_representation(instance)
        extra = instance.extra or {}

        # About
        rep["subtext"] = extra.get("subtext", {"sw": "", "en": ""})
        rep["mission"] = extra.get("mission", {"sw": "", "en": ""})
        rep["vision"] = extra.get("vision", {"sw": "", "en": ""})
        rep["values"] = extra.get("values", [])
        rep["team"] = extra.get("team", [])

        # Terms / Privacy
        rep["subtitle"] = extra.get("subtitle", {"sw": "", "en": ""})
        rep["sections"] = extra.get("sections", [])

        # Help (content tayari ipo kwenye rep kupitia get_content)
        # lastUpdated
        rep["lastUpdated"] = instance.updated_at.isoformat() if instance.updated_at else ""

        return rep

    def update(self, instance, validated_data):
        """
        Shughulikia `extra` fields (subtext, mission, vision, values,
        team, subtitle, sections) kwa kuwaweka kwenye `extra` JSON.
        """
        # Vuta data ya awali ya extra
        extra = dict(instance.extra or {})

        # About fields
        for field in ("subtext", "mission", "vision"):
            if field in self.initial_data:
                extra[field] = self.initial_data[field]

        # values / team (About)
        for field in ("values", "team"):
            if field in self.initial_data:
                extra[field] = self.initial_data[field]

        # Terms / Privacy
        if "subtitle" in self.initial_data:
            extra["subtitle"] = self.initial_data["subtitle"]
        if "sections" in self.initial_data:
            extra["sections"] = self.initial_data["sections"]

        # Help: content tayari inashughulikiwa na to_internal_value
        # (content_sw / content_en)

        instance.extra = extra

        # Shughulikia heading_sw / heading_en / content_sw / content_en
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class BannerSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    subtitle = serializers.SerializerMethodField()
    ctaText = serializers.SerializerMethodField()
    ordering = serializers.IntegerField(source="order", read_only=True)

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
            "cta_link", "image_url", "active", "order", "ordering", "created_at",
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
            "id",
            "name",
            "location",
            "quote",
            "avatar_url",
            "rating",
            "active",
            "order",
            "created_at",
            "quote_sw",
            "quote_en",
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