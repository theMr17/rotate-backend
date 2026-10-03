from django.db import transaction
from django.utils import timezone

from .models import Offer, Order


class OrderError(Exception):
    pass


BLOCKING_STATUSES = [Order.Status.ACCEPTED, Order.Status.ACTIVE]


def overlapping_bookings(item, start_time, end_time):
    return Order.objects.filter(
        item=item,
        status__in=BLOCKING_STATUSES,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )


def request_rental(borrower, item, start_time, end_time, hourly_rate, message=''):
    if item.owner_id == borrower.id:
        raise OrderError("You can't rent your own item.")
    if start_time < timezone.now():
        raise OrderError('Start time must be in the future.')
    if end_time <= start_time:
        raise OrderError('End time must be after start time.')
    if overlapping_bookings(item, start_time, end_time).exists():
        raise OrderError('Item is already booked for this time.')

    with transaction.atomic():
        order = Order.objects.create(
            item=item,
            borrower=borrower,
            lender=item.owner,
            start_time=start_time,
            end_time=end_time,
        )
        Offer.objects.create(
            order=order, proposed_by=borrower, hourly_rate=hourly_rate, message=message
        )
    return order