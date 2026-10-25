import secrets

from django.conf import settings
from django.db import IntegrityError, models, transaction

BOOKING_REF_PREFIX = 'ROT-'
# Crockford base32: digits + letters minus I, L, O, U, so refs are easy to read aloud
# and hard to mistype. 6 chars = 32**6 ~ 1.07 billion refs.
BOOKING_REF_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
BOOKING_REF_LENGTH = 6
BOOKING_REF_ATTEMPTS = 5


def generate_booking_ref():
    code = ''.join(secrets.choice(BOOKING_REF_ALPHABET) for _ in range(BOOKING_REF_LENGTH))
    return f'{BOOKING_REF_PREFIX}{code}'


class BookingRefUnavailable(Exception):
    pass


class InvalidTransition(Exception):
    pass

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

    ALLOWED_TRANSITIONS = {
        Status.REQUESTED: {Status.ACCEPTED, Status.REJECTED, Status.CANCELLED},
        Status.ACCEPTED: {Status.ACTIVE, Status.CANCELLED},
        Status.ACTIVE: {Status.RETURNED},
        Status.RETURNED: {Status.COMPLETED, Status.DISPUTED},
        Status.DISPUTED: {Status.COMPLETED},
        Status.REJECTED: set(),
        Status.CANCELLED: set(),
        Status.COMPLETED: set(),
    }
            

    booking_ref = models.CharField(max_length=16, unique=True, editable=False)
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
    rental_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_due = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='orders_cancelled',
    )
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
        return f'Order {self.booking_ref or self.pk} ({self.status})'

    def save(self, *args, **kwargs):
        if self.booking_ref:
            return super().save(*args, **kwargs)
        
        for _ in range(BOOKING_REF_ATTEMPTS):
            self.booking_ref = generate_booking_ref()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as error:
                if 'booking_ref' not in str(error):
                    self.booking_ref = ''
                    raise
        
        self.booking_ref = ''
        raise BookingRefUnavailable(
            'Could not allocate a booking reference. Please try again.'
        )
    
    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS[self.status]

    def transition_to(self, new_status, **fields):
        """Move to new_status, saving any extra fields (e.g. timestamps) in the same write."""
        if not self.can_transition_to(new_status):
            raise InvalidTransition(
                f'Cannot move order #{self.pk} from {self.status} to {new_status}.'
            )
        self.status = new_status
        for name, value in fields.items():
            setattr(self, name, value)
        self.save(update_fields=['status', 'updated_at', *fields])

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
        return f'Offer ₹{self.hourly_rate}/hr on Order #{self.order_id} ({self.status})'