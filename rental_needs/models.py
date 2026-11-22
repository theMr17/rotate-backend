from django.conf import settings
from django.db import models


class RentalNeed(models.Model):

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"

    # User who posted the rental requirement
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rental_needs",
    )

    # Description of what the user needs
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=100, default="Other")

    # Rental duration
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    # Where the user needs the item
    location = models.CharField(max_length=255)

    # Maximum hourly budget (optional)
    budget_per_hour = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    # The Order corresponding to the offer ultimately accepted
    fulfilled_order = models.OneToOneField(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fulfilled_rental_need",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    end_time__gt=models.F("start_time")
                ),
                name="rneed_end_after_start",
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(budget_per_hour__isnull=True)
                    | models.Q(budget_per_hour__gt=0)
                ),
                name="rneed_budget_positive",
            ),
        ]

        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="rneed_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.requester.name}"


class RentalNeedResponse(models.Model):

    # Which rental requirement this response belongs to
    rental_need = models.ForeignKey(
        RentalNeed,
        on_delete=models.CASCADE,
        related_name="responses",
    )

    # User who is offering to fulfil the requirement
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rental_need_responses",
    )

    # The actual Order created for this response
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="rental_need_response",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["rental_need", "provider"],
                name="rneed_provider_once",
            ),
        ]

    def __str__(self):
        return (
            f"Response by {self.provider.name} "
            f"to RentalNeed #{self.rental_need_id}"
        )