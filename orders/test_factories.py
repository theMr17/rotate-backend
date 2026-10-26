import pytest

from items.factories import ItemFactory
from orders.factories import OfferFactory, OrderFactory
from orders.models import Offer, Order
from user.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def test_user_factory_sets_usable_password():
    user = UserFactory()
    assert user.check_password(DEFAULT_PASSWORD)
    assert UserFactory().email != user.email


def test_item_factory_creates_owner():
    item = ItemFactory()
    assert item.owner.pk is not None
    assert item.status == 'AVAILABLE'


def test_requested_order_matches_request_rental_invariants():
    order = OrderFactory()
    assert order.booking_ref.startswith('ROT-')
    assert order.lender == order.item.owner
    assert order.borrower != order.lender
    assert order.deposit_amount == order.item.deposit_amount
    assert order.agreed_hourly_rate is None
    offer = order.offers.get()
    assert offer.status == Offer.Status.PENDING
    assert offer.proposed_by == order.borrower


def test_order_offer_can_be_skipped_or_customised():
    assert not OrderFactory(offer=False).offers.exists()
    order = OrderFactory(offer__message='Can you do 35?')
    assert order.offers.get().message == 'Can you do 35?'


def test_non_requested_order_has_agreed_rate_and_no_offer():
    order = OrderFactory(status=Order.Status.ACCEPTED)
    assert order.agreed_hourly_rate is not None
    assert not order.offers.exists()


def test_offer_factory_builds_its_own_order():
    offer = OfferFactory()
    assert offer.order.offers.get() == offer
