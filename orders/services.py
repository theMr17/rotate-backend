from django.db import transaction
from django.utils import timezone

from .models import Offer, Order
from items.models import Item


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


def _pending_offer(order):
    offer = order.offers.filter(status=Offer.Status.PENDING).first()
    if offer is None:
        raise OrderError('No pending offer on this order.')
    return offer


def _check_can_respond(order, user, offer):
    if user.id not in (order.borrower_id, order.lender_id):
        raise OrderError('You are not part of this order.')
    if offer.proposed_by_id == user.id:
        raise OrderError('Wait for the other person to respond to your offer.')


def counter_offer(order, user, hourly_rate, message=''):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.REQUESTED:
            raise OrderError('This order is no longer open for negotiation.')
        offer = _pending_offer(order)
        _check_can_respond(order, user, offer)

        offer.status = Offer.Status.COUNTERED
        offer.save(update_fields=['status'])
        return Offer.objects.create(
            order=order, proposed_by=user, hourly_rate=hourly_rate, message=message
        )


def accept_offer(order, user):
    with transaction.atomic():
        Item.objects.select_for_update().get(pk=order.item_id)
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.REQUESTED:
            raise OrderError('This order is no longer open for negotiation.')
        offer = _pending_offer(order)
        _check_can_respond(order, user, offer)
        if overlapping_bookings(order.item, order.start_time, order.end_time).exists():
            raise OrderError('Item is already booked for this time.')

        offer.status = Offer.Status.ACCEPTED
        offer.save(update_fields=['status'])
        order.agreed_hourly_rate = offer.hourly_rate
        order.save(update_fields=['agreed_hourly_rate'])
        order.transition_to(Order.Status.ACCEPTED)

        clashing = Order.objects.filter(
            item_id=order.item_id,
            status=Order.Status.REQUESTED,
            start_time__lt=order.end_time,
            end_time__gt=order.start_time,
        ).exclude(pk=order.pk)
        for other in clashing:
            other.offers.filter(status=Offer.Status.PENDING).update(
                status=Offer.Status.REJECTED
            )
            other.transition_to(Order.Status.REJECTED)
    return order


def reject_offer(order, user):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.REQUESTED:
            raise OrderError('This order is no longer open for negotiation.')
        offer = _pending_offer(order)
        _check_can_respond(order, user, offer)

        offer.status = Offer.Status.REJECTED
        offer.save(update_fields=['status'])
        order.transition_to(Order.Status.REJECTED)
    return order