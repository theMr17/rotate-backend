from django.conf import settings
from django.db import models


class Item(models.Model):
    CONDITION_CHOICES = [
        ("NEW", "New"),
        ("GOOD", "Good"),
        ("FAIR", "Fair"),
        ("POOR", "Poor"),
    ]

    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("UNAVAILABLE", "Unavailable"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="items",
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=100, default="Other")

    # Use the same field name as the original migration
    # and the Orders/Offers pricing terminology.
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default = 0,
    )

    condition = models.CharField(
        max_length=10,
        choices=CONDITION_CHOICES,
        default = "GOOD",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="AVAILABLE",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hourly_rate__gt=0),
                name="item_hourly_rate_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(deposit_amount__gte=0),
                name="item_deposit_nonnegative",
            ),
        ]

    def __str__(self):
        return self.title