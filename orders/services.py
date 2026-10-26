from django.db import transaction
from django.utils import timezone

from . import pricing
from .models import Offer, Order
from items.models import Item


class OrderError(Exception):
    """The request is invalid for the order's current state (HTTP 400)."""


class OrderPermissionError(OrderError):
    """The user is part of the order but not allowed to take this action (HTTP 403)."""


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
    if item.status != "AVAILABLE":
        raise OrderError("This item is not currently available for rental.")
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
            deposit_amount=item.deposit_amount,
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
        item = Item.objects.select_for_update().get(pk=order.item_id)
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.item = item
        if order.status != Order.Status.REQUESTED:
            raise OrderError('This order is no longer open for negotiation.')
        offer = _pending_offer(order)
        _check_can_respond(order, user, offer)
        if order.item.status != 'AVAILABLE':
            raise OrderError('This item is no longer available for rental.')
        if overlapping_bookings(order.item, order.start_time, order.end_time).exists():
            raise OrderError('Item is already booked for this time.')

        offer.status = Offer.Status.ACCEPTED
        offer.save(update_fields=['status'])
        breakdown = pricing.calculate(
            offer.hourly_rate, order.start_time, order.end_time, order.deposit_amount
        )
        order.transition_to(
            Order.Status.ACCEPTED,
            agreed_hourly_rate=offer.hourly_rate,
            rental_fee=breakdown.rental_fee,
            platform_fee=breakdown.platform_fee,
            total_due=breakdown.total_due,
        )

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

BORROWER = 'borrower'
LENDER = 'lender'

# action -> (roles that may perform it, statuses it may be performed from).
# Single source of truth for both enforcement and `allowed_actions`.
LIFECYCLE_RULES = {
    'cancel': ((BORROWER, LENDER), (Order.Status.REQUESTED, Order.Status.ACCEPTED)),
    'start': ((LENDER,), (Order.Status.ACCEPTED,)),
    'return': ((BORROWER,), (Order.Status.ACTIVE,)),
    'complete': ((LENDER,), (Order.Status.RETURNED,)),
    'dispute': ((BORROWER, LENDER), (Order.Status.RETURNED,)),
}
ACTION_ORDER = ['accept', 'counter', 'reject', 'cancel', 'start', 'return', 'complete', 'dispute']


def role_of(order, user):
    if user.id == order.borrower_id:
        return BORROWER
    if user.id == order.lender_id:
        return LENDER
    return None


def allowed_actions(order, user):
    """Actions `user` may take on `order` right now, mirroring the service checks.

    Uses prefetched offers and the joined item, so it adds no queries. Overlap with
    other bookings is only checked when `accept` is actually called.
    """
    role = role_of(order, user)
    if role is None:
        return []
    actions = set()
    if order.status == Order.Status.REQUESTED:
        pending = next((o for o in order.offers.all() if o.status == Offer.Status.PENDING), None)
        if pending is not None and pending.proposed_by_id != user.id:
            actions |= {'counter', 'reject'}
            if order.item.status == 'AVAILABLE':
                actions.add('accept')
    for name, (roles, statuses) in LIFECYCLE_RULES.items():
        if role in roles and order.status in statuses:
            actions.add(name)
    return [name for name in ACTION_ORDER if name in actions]


def _lock(order):
    return Order.objects.select_for_update().get(pk=order.pk)


def _check_role(order, user, roles, action):
    allowed = (
        (BORROWER in roles and user.id == order.borrower_id)
        or (LENDER in roles and user.id == order.lender_id)
    )
    if allowed:
        return
    if user.id not in (order.borrower_id, order.lender_id):
        raise OrderPermissionError('You are not part of this order.')
    who = ' or '.join(f'the {role}' for role in roles)
    raise OrderPermissionError(f'Only {who} can {action} this order.')


def _check_status(order, allowed_from, action):
    if order.status not in allowed_from:
        expected = ' or '.join(str(status) for status in allowed_from)
        raise OrderError(
            f"Can't {action} an order that is {order.status}; it must be {expected}."
        )


def _check_rule(order, user, action, verb):
    roles, statuses = LIFECYCLE_RULES[action]
    _check_role(order, user, roles, verb)
    _check_status(order, statuses, action)


def cancel_order(order, user):
    """Either party may cancel before the handover (requested or accepted)."""
    with transaction.atomic():
        order = _lock(order)
        _check_rule(order, user, 'cancel', 'cancel')
        order.offers.filter(status=Offer.Status.PENDING).update(status=Offer.Status.REJECTED)
        order.transition_to(Order.Status.CANCELLED, cancelled_by=user)
    return order


def start_order(order, user):
    """The lender confirms the item has been handed over."""
    with transaction.atomic():
        order = _lock(order)
        _check_rule(order, user, 'start', 'confirm handover for')
        order.transition_to(Order.Status.ACTIVE, started_at=timezone.now())
    return order


def return_order(order, user):
    """The borrower marks the item as returned."""
    with transaction.atomic():
        order = _lock(order)
        _check_rule(order, user, 'return', 'mark as returned')
        order.transition_to(Order.Status.RETURNED, returned_at=timezone.now())
    return order


def complete_order(order, user):
    """The lender confirms the item came back fine.

    Disputed orders are not completed here: resolving a dispute is a moderation
    step, not something either party can do unilaterally.
    """
    with transaction.atomic():
        order = _lock(order)
        _check_rule(order, user, 'complete', 'complete')
        order.transition_to(Order.Status.COMPLETED, completed_at=timezone.now())
    return order


def dispute_order(order, user):
    """Either party may raise a dispute once the item is marked returned."""
    with transaction.atomic():
        order = _lock(order)
        _check_rule(order, user, 'dispute', 'dispute')
        order.transition_to(Order.Status.DISPUTED)
    return order
