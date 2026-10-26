from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from items.factories import ItemFactory
from orders.models import Offer, Order
from user.factories import UserFactory


class OrderFactory(factory.django.DjangoModelFactory):
    """An order one day out, for three hours.

    Mirrors orders.services.request_rental: the lender is the item's owner, the
    deposit is copied from the item, and a REQUESTED order gets a pending offer
    (pass ``offer=False`` to skip it). Any other status gets an agreed rate.
    """

    class Meta:
        model = Order
        skip_postgeneration_save = True

    item = factory.SubFactory(ItemFactory)
    borrower = factory.SubFactory(UserFactory)
    lender = factory.SelfAttribute('item.owner')
    start_time = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))
    end_time = factory.LazyAttribute(lambda o: o.start_time + timedelta(hours=3))
    status = Order.Status.REQUESTED
    deposit_amount = factory.SelfAttribute('item.deposit_amount')
    agreed_hourly_rate = factory.LazyAttribute(
        lambda o: None if o.status == Order.Status.REQUESTED else Decimal('40.00')
    )

    @factory.post_generation
    def offer(order, create, extracted, **kwargs):
        if not create or extracted is False or order.status != Order.Status.REQUESTED:
            return
        OfferFactory(order=order, **kwargs)


class OfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Offer

    order = factory.SubFactory(OrderFactory, offer=False)
    proposed_by = factory.SelfAttribute('order.borrower')
    hourly_rate = Decimal('40.00')
