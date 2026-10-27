from django.db import transaction
from django.utils import timezone

from items.models import Item
from orders.models import Order, Offer
from orders.services import overlapping_bookings

from .models import RentalNeed, RentalNeedResponse


class RentalNeedError(Exception):
    """Invalid rental need operation."""


class RentalNeedPermissionError(RentalNeedError):
    """User is not allowed to perform this operation."""


@transaction.atomic
def respond_to_need(need_id, provider, item_id, hourly_rate, message=""):

    # Lock the need to prevent conflicting operations.
    need = (
        RentalNeed.objects
        .select_for_update()
        .select_related("requester")
        .get(pk=need_id)
    )

    # A provider cannot respond to a closed request.
    if need.status != RentalNeed.Status.OPEN:
        raise RentalNeedError(
            "This rental request is no longer open."
        )

    # Requester cannot respond to their own need.
    if need.requester_id == provider.id:
        raise RentalNeedPermissionError(
            "You cannot respond to your own rental request."
        )

    # The requested rental period must still be valid.
    if need.start_time <= timezone.now():
        raise RentalNeedError(
            "The requested rental start time has passed."
        )

    # Lock the selected item while validating it.
    try:
        item = Item.objects.select_for_update().get(pk=item_id)
    except Item.DoesNotExist:
        raise RentalNeedError(
            "The selected item does not exist."
        )

    # Only the owner can offer their item.
    if item.owner_id != provider.id:
        raise RentalNeedPermissionError(
            "You can only offer items that you own."
        )

    if item.status != "AVAILABLE":
        raise RentalNeedError(
            "This item is currently unavailable."
        )

    # Prevent offering an already-booked item.
    if overlapping_bookings(
        item,
        need.start_time,
        need.end_time
    ).exists():
        raise RentalNeedError(
            "This item is already booked for the requested period."
        )

    # One response per provider per rental need.
    if RentalNeedResponse.objects.filter(
        rental_need=need,
        provider=provider
    ).exists():
        raise RentalNeedError(
            "You have already responded to this rental request."
        )

    # Create a normal Order.
    order = Order.objects.create(
        item=item,
        borrower=need.requester,
        lender=provider,
        start_time=need.start_time,
        end_time=need.end_time,
        deposit_amount=item.deposit_amount,
    )

    # The provider makes the initial offer.
    offer = Offer.objects.create(
        order=order,
        proposed_by=provider,
        hourly_rate=hourly_rate,
        message=message,
    )

    # Connect this response to the RentalNeed and Order.
    response = RentalNeedResponse.objects.create(
        rental_need=need,
        provider=provider,
        order=order,
    )

    return response