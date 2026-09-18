from rest_framework import serializers

from .models import Banner, FAQ, SiteContent, Testimonial


class SiteContentSerializer(serializers.ModelSerializer):
    heading = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()

    class Meta:
        model = SiteContent
        fields = [
            "id", "key", "heading", "content", "extra", "updated_at",
        ]

    def get_heading(self, obj):
        return {"sw": obj.heading_sw, "en": obj.heading_en}

    def get_content(self, obj):
        return {"sw": obj.content_sw, "en": obj.content_en}


class BannerSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    subtitle = serializers.SerializerMethodField()
    ctaText = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = [
            "id", "title", "subtitle", "ctaText",
            "cta_link", "image_url", "active", "order", "created_at",
        ]

    def get_title(self, obj):
        return {"sw": obj.title_sw, "en": obj.title_en}

    def get_subtitle(self, obj):
        return {"sw": obj.subtitle_sw, "en": obj.subtitle_en}

    def get_ctaText(self, obj):
        return {"sw": obj.cta_text_sw, "en": obj.cta_text_en}


class TestimonialSerializer(serializers.ModelSerializer):
    quote = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = [
            "id", "name", "quote", "avatar_url", "rating",
            "active", "created_at",
        ]

    def get_quote(self, obj):
        return {"sw": obj.quote_sw, "en": obj.quote_en}


class FAQSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()
    answer = serializers.SerializerMethodField()

    class Meta:
        model = FAQ
        fields = [
            "id", "question", "answer", "active", "order", "created_at",
        ]

    def get_question(self, obj):
        return {"sw": obj.question_sw, "en": obj.question_en}

    def get_answer(self, obj):
        return {"sw": obj.answer_sw, "en": obj.answer_en}