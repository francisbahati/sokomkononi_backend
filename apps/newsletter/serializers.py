from rest_framework import serializers


class NewsletterSubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    lang = serializers.ChoiceField(
        choices=["sw", "en"], required=False, allow_blank=True, default="",
    )
    source = serializers.CharField(
        max_length=40, required=False, allow_blank=True, default="homepage",
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_source(self, value):
        return (value or "homepage").strip()[:40]


class NewsletterUnsubscribeSerializer(serializers.Serializer):
    token = serializers.UUIDField()
