from django.conf import settings
from django.db import models


class Review(models.Model):
    class Role(models.TextChoices):
        LENDER = 'lender', 'Lender'
        BORROWER = 'borrower', 'Borrower'

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_given'
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_received'
    )
    reviewee_role = models.CharField(max_length=10, choices=Role.choices)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['order', 'reviewer'], name='one_review_per_order_per_reviewer'),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_1_to_5'
            ),
        ]
        indexes = [models.Index(fields=['reviewee', 'reviewee_role'])]

    def __str__(self):
        return f'{self.rating}* for {self.reviewee_id} on order {self.order_id}'


class ReliabilityStats(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reliability'
    )
    score = models.PositiveSmallIntegerField(null=True, blank=True)  # 0-100
    rentals_counted = models.PositiveIntegerField(default=0)
    on_time_returns = models.PositiveIntegerField(default=0)
    late_returns = models.PositiveIntegerField(default=0)
    late_cancellations = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'reliability stats'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(score__isnull=True) | models.Q(score__lte=100),
                name='reliability_score_0_to_100',
            ),
        ]

    def __str__(self):
        return f'Reliability for {self.user_id}: {self.score}'
