from django.db import models


class SiteContent(models.Model):
    """
    A simple key-value store for singleton content blocks:
    About, Terms, Privacy, Help.
    """

    class Key(models.TextChoices):
        ABOUT = "ABOUT", "About"
        TERMS = "TERMS", "Terms"
        PRIVACY = "PRIVACY", "Privacy"
        HELP = "HELP", "Help"

    key = models.CharField(max_length=20, choices=Key.choices, unique=True)

    heading_sw = models.CharField(max_length=255, blank=True)
    heading_en = models.CharField(max_length=255, blank=True)

    content_sw = models.TextField(blank=True)
    content_en = models.TextField(blank=True)

    # Extra structure for About (mission + subtext + values)
    extra = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "site_content"
        ordering = ["key"]

    def __str__(self):
        return self.get_key_display()


class Banner(models.Model):
    title_sw = models.CharField(max_length=255, blank=True)
    title_en = models.CharField(max_length=255, blank=True)
    subtitle_sw = models.CharField(max_length=255, blank=True)
    subtitle_en = models.CharField(max_length=255, blank=True)
    cta_text_sw = models.CharField(max_length=100, blank=True)
    cta_text_en = models.CharField(max_length=100, blank=True)
    cta_link = models.CharField(max_length=500, blank=True)
    image_url = models.URLField(blank=True)
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_banners"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title_sw or self.title_en or f"Banner #{self.pk}"


class Testimonial(models.Model):
    name = models.CharField(max_length=150)
    quote_sw = models.TextField(blank=True)
    quote_en = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_testimonials"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class FAQ(models.Model):
    question_sw = models.CharField(max_length=255)
    question_en = models.CharField(max_length=255, blank=True)
    answer_sw = models.TextField()
    answer_en = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_faqs"
        ordering = ["order", "id"]

    def __str__(self):
        return self.question_sw or self.question_en