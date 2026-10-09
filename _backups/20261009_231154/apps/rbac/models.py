from django.conf import settings
from django.db import models


class Role(models.Model):
    """
    A role bundles a set of permission keys.
    """

    key = models.SlugField(max_length=60, unique=True)
    label_sw = models.CharField(max_length=100)
    label_en = models.CharField(max_length=100)
    description_sw = models.CharField(max_length=255, blank=True)
    description_en = models.CharField(max_length=255, blank=True)
    permissions = models.JSONField(default=list, blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "roles"
        ordering = ["key"]

    def __str__(self):
        return self.label_sw or self.key


class StaffAssignment(models.Model):
    """
    A sub-admin user + their role.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_assignment",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    active = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_assignments"
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} → {self.role.key}"