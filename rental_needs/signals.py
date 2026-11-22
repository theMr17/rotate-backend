from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from orders.models import Offer, Order
from orders.services import OrderError

from .models import RentalNeed, RentalNeedResponse


def close_competing_orders(need_id, winning_order_id):
    """
    Reject all other outstanding Orders associated with
    a RentalNeed after one provider's offer is accepted.
    """

    other_response_order_ids = (
        RentalNeedResponse.objects
        .filter(rental_need_id=need_id)
        .exclude(order_id=winning_order_id)
        .values("order_id")
    )

    with transaction.atomic():

        competing_orders = (
            Order.objects
            .select_for_update()
            .filter(
                pk__in=other_response_order_ids,
                status=Order.Status.REQUESTED,
            )
        )

        for order in competing_orders:

            # Reject any currently pending offers.
            order.offers.filter(
                status=Offer.Status.PENDING
            ).update(
                status=Offer.Status.REJECTED
            )

            # Transition the competing Order.
            order.transition_to(Order.Status.REJECTED)


@receiver(post_save, sender=Offer)
def handle_accepted_rental_need_offer(
    sender,
    instance,
    created,
    update_fields=None,
    **kwargs,
):
    """
    When an Offer belonging to a RentalNeed is accepted:

    1. Mark the RentalNeed as fulfilled.
    2. Associate it with the winning Order.
    3. After commit, reject competing Orders.
    """

    # Ignore newly created offers and unrelated updates.
    if created or instance.status != Offer.Status.ACCEPTED:
        return

    if update_fields is not None and "status" not in update_fields:
        return

    # Check whether this Order originated from a RentalNeed.
    response = (
        RentalNeedResponse.objects
        .filter(order_id=instance.order_id)
        .values("rental_need_id")
        .first()
    )

    # Ordinary Orders should behave exactly as before.
    if response is None:
        return

    need_id = response["rental_need_id"]

    # Atomically claim the RentalNeed.
    # Only one accepted Order can successfully fulfil it.
    updated = RentalNeed.objects.filter(
        pk=need_id,
        status=RentalNeed.Status.OPEN,
    ).update(
        status=RentalNeed.Status.FULFILLED,
        fulfilled_order_id=instance.order_id,
        updated_at=timezone.now(),
    )

    if updated == 0:

        # Allow an idempotent save for the already selected Order.
        need = RentalNeed.objects.only(
            "fulfilled_order_id"
        ).get(pk=need_id)

        if need.fulfilled_order_id == instance.order_id:
            return

        # This acceptance loses if another provider already won.
        raise OrderError(
            "This rental request has already been fulfilled. "
            "The offer can no longer be accepted."
        )

    # Run cleanup only after the acceptance transaction commits.
    transaction.on_commit(
        lambda: close_competing_orders(
            need_id,
            instance.order_id,
        ),
        robust=True,
    )