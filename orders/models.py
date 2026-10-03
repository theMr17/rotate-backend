from django.db import models
from django.conf import settings

class Order(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'
        ACTIVE = 'active', 'Active'
        RETURNED = 'returned', 'Returned'
        DISPUTED = 'disputed', 'Disputed'
        COMPLETED = 'completed', 'Completed'

    item = models.ForeignKey(
        'items.Item', on_delete=models.PROTECT, related_name='orders'
    )
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders_as_borrower'
    )
    lender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders_as_lender'
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REQUESTED
    )
    agreed_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F('start_time')),
                name='order_end_after_start',
            ),
        ]

    def __str__(self):
        return f'Order #{self.pk} ({self.status})'

class Offer(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        COUNTERED = 'countered', 'Countered'
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='offers')
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='offers_made')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=models.Q(status='pending'),
                name='one_pending_offer_per_order',
            ),
            models.CheckConstraint(
                condition=models.Q(hourly_rate__gt=0),
                name='offer_rate_positive',
            ),
        ]

    def __str__(self):
        return f'Offer Rs{self.hourly_rate}/hr on Order #{self.order_id} ({self.status})'
