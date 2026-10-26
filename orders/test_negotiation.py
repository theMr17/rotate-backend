"""Rental requests and offer negotiation (orders.services, through the API).

Covers request_rental's guards and overlap rules, counter/accept/reject
turn-taking, auto-rejection of clashing requests on accept, and the row locking
that stops two clashing requests from both being accepted.
"""
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from items.factories import ItemFactory
from orders import pricing, services
from orders.factories import OrderFactory
from orders.models import Offer, Order
from user.factories import UserFactory

pytestmark = pytest.mark.django_db

S = Order.Status
O = Offer.Status
BLOCKING = {S.ACCEPTED, S.ACTIVE}
# Midnight two days out, so at(10) .. at(15) are all in the future and on one day.
T0 = (timezone.now() + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)


def at(hour, minute=0):
    return T0 + timedelta(hours=hour, minutes=minute)


@pytest.fixture
def item():
    return ItemFactory()


@pytest.fixture
def lender(item):
    return item.owner


@pytest.fixture
def borrower():
    return UserFactory()


def call(client, user, url, data=None):
    client.force_authenticate(user)
    return client.post(url, data or {}, format='json')


def act(client, user, order, action, data=None):
    return call(client, user, reverse(f'order-{action}', args=[order.pk]), data)


def request(client, borrower, item, start, end, rate='40.00', message=''):
    return call(client, borrower, reverse('order-list'), {
        'item': item.pk,
        'start_time': start.isoformat(),
        'end_time': end.isoformat(),
        'hourly_rate': rate,
        'message': message,
    })


def booking(item, start, end, status=S.REQUESTED, **kwargs):
    return OrderFactory(item=item, start_time=start, end_time=end, status=status, **kwargs)


def offers(order):
    return list(order.offers.order_by('created_at', 'pk').values_list('proposed_by', 'hourly_rate', 'status'))


def snapshot(order):
    return Order.objects.filter(pk=order.pk).values().get(), offers(order)


# --- request_rental ---------------------------------------------------------

def test_request_creates_order_with_opening_offer(api_client, item, lender, borrower):
    response = request(api_client, borrower, item, at(10), at(13), rate='45.00', message='Weekend?')

    assert response.status_code == 201, response.data
    order = Order.objects.get(pk=response.data['id'])
    assert order.status == S.REQUESTED
    assert (order.borrower, order.lender) == (borrower, lender)
    assert order.deposit_amount == item.deposit_amount
    assert order.agreed_hourly_rate is None
    offer = order.offers.get()
    assert (offer.proposed_by, offer.hourly_rate, offer.status, offer.message) == (
        borrower, Decimal('45.00'), O.PENDING, 'Weekend?',
    )


@pytest.mark.parametrize('case, message', [
    ('own_item', "can't rent your own item"),
    ('unavailable', 'not currently available'),
    ('past_start', 'must be in the future'),
    ('end_equals_start', 'End time must be after start time'),
    ('end_before_start', 'End time must be after start time'),
])
def test_request_guards(api_client, item, lender, borrower, case, message):
    who, start, end = borrower, at(10), at(13)
    if case == 'own_item':
        who = lender
    elif case == 'unavailable':
        item.status = 'UNAVAILABLE'
        item.save()
    elif case == 'past_start':
        start, end = timezone.now() - timedelta(minutes=1), timezone.now() + timedelta(hours=2)
    elif case == 'end_equals_start':
        end = start
    elif case == 'end_before_start':
        end = start - timedelta(hours=1)

    response = request(api_client, who, item, start, end)

    assert response.status_code == 400
    assert message in response.data['detail']
    assert not Order.objects.exists()
    assert not Offer.objects.exists()


@pytest.mark.parametrize('status', list(S))
def test_only_accepted_and_active_bookings_block_new_requests(api_client, item, borrower, status):
    booking(item, at(10), at(13), status=status)

    response = request(api_client, borrower, item, at(11), at(12))

    if status in BLOCKING:
        assert response.status_code == 400
        assert 'already booked' in response.data['detail']
        assert Order.objects.count() == 1
    else:
        assert response.status_code == 201, response.data


@pytest.mark.parametrize('start, end, clashes', [
    (at(9), at(10), False),            # ends exactly when the booking starts
    (at(13), at(14), False),           # starts exactly when the booking ends
    (at(9), at(10, 1), True),          # overlaps the start by a minute
    (at(12, 59), at(14), True),        # overlaps the end by a minute
    (at(11), at(12), True),            # inside
    (at(9), at(14), True),             # contains
    (at(10), at(13), True),            # identical
])
def test_overlap_boundaries(api_client, item, borrower, start, end, clashes):
    booking(item, at(10), at(13), status=S.ACCEPTED)

    response = request(api_client, borrower, item, start, end)

    assert response.status_code == (400 if clashes else 201), response.data


def test_booking_on_another_item_does_not_block(api_client, item, borrower):
    booking(ItemFactory(), at(10), at(13), status=S.ACCEPTED)

    assert request(api_client, borrower, item, at(10), at(13)).status_code == 201


# --- turn-taking ------------------------------------------------------------

def test_negotiation_alternates_until_accepted(api_client, item, lender, borrower):
    order = booking(item, at(10), at(13), borrower=borrower, offer__hourly_rate=Decimal('30.00'))

    # The borrower made the opening offer, so it's the lender's turn.
    for action in ('counter', 'accept', 'reject'):
        response = act(api_client, borrower, order, action, {'hourly_rate': '31.00'})
        assert response.status_code == 400
        assert 'Wait for the other person' in response.data['detail']

    assert act(api_client, lender, order, 'counter', {'hourly_rate': '45.00'}).status_code == 200
    # Now it's the borrower's turn; the lender can't respond to their own counter.
    assert act(api_client, lender, order, 'counter', {'hourly_rate': '44.00'}).status_code == 400
    assert act(api_client, lender, order, 'accept').status_code == 400

    response = act(api_client, borrower, order, 'counter', {'hourly_rate': '38.00', 'message': 'Meet halfway?'})
    assert response.status_code == 200, response.data
    assert response.data['allowed_actions'] == ['cancel']  # borrower is waiting again

    response = act(api_client, lender, order, 'accept')
    assert response.status_code == 200, response.data

    order.refresh_from_db()
    assert order.status == S.ACCEPTED
    assert order.agreed_hourly_rate == Decimal('38.00')
    assert offers(order) == [
        (borrower.pk, Decimal('30.00'), O.COUNTERED),
        (lender.pk, Decimal('45.00'), O.COUNTERED),
        (borrower.pk, Decimal('38.00'), O.ACCEPTED),
    ]
    assert order.offers.get(status=O.ACCEPTED).message == 'Meet halfway?'


def test_counter_replaces_pending_offer(api_client, item, lender, borrower):
    order = booking(item, at(10), at(13), borrower=borrower)

    act(api_client, lender, order, 'counter', {'hourly_rate': '55.00', 'message': 'Busy weekend'})

    pending = order.offers.get(status=O.PENDING)
    assert (pending.proposed_by, pending.hourly_rate, pending.message) == (lender, Decimal('55.00'), 'Busy weekend')
    assert order.offers.filter(status=O.COUNTERED).count() == 1
    order.refresh_from_db()
    assert order.status == S.REQUESTED


@pytest.mark.parametrize('data', [{}, {'hourly_rate': '0.00'}, {'hourly_rate': '-1'}, {'hourly_rate': 'abc'}])
def test_counter_validation(api_client, item, lender, data):
    order = booking(item, at(10), at(13))
    before = snapshot(order)

    response = act(api_client, lender, order, 'counter', data)

    assert response.status_code == 400
    assert 'hourly_rate' in response.data
    assert snapshot(order) == before


def test_borrower_can_accept_lenders_counter(api_client, item, lender, borrower):
    order = booking(item, at(10), at(13), borrower=borrower)
    act(api_client, lender, order, 'counter', {'hourly_rate': '42.50'})

    response = act(api_client, borrower, order, 'accept')

    assert response.status_code == 200, response.data
    order.refresh_from_db()
    assert order.status == S.ACCEPTED
    assert order.agreed_hourly_rate == Decimal('42.50')


def test_accept_snapshots_pricing(api_client, item, lender):
    order = booking(item, at(10), at(12, 30), offer__hourly_rate=Decimal('40.00'))

    act(api_client, lender, order, 'accept')

    order.refresh_from_db()
    expected = pricing.calculate(Decimal('40.00'), order.start_time, order.end_time, order.deposit_amount)
    assert (order.rental_fee, order.platform_fee, order.total_due) == (
        expected.rental_fee, expected.platform_fee, expected.total_due,
    )
    assert order.rental_fee == Decimal('120.00')  # 2.5h rounds up to 3 billable hours


@pytest.mark.parametrize('responder', ['lender', 'borrower'])
def test_reject_closes_the_order(api_client, item, lender, borrower, responder):
    order = booking(item, at(10), at(13), borrower=borrower)
    if responder == 'borrower':
        act(api_client, lender, order, 'counter', {'hourly_rate': '60.00'})

    response = act(api_client, {'lender': lender, 'borrower': borrower}[responder], order, 'reject')

    assert response.status_code == 200, response.data
    order.refresh_from_db()
    assert order.status == S.REJECTED
    assert not order.offers.filter(status=O.PENDING).exists()
    assert order.offers.order_by('-created_at', '-pk').first().status == O.REJECTED
    assert order.agreed_hourly_rate is None
    assert response.data['allowed_actions'] == []


@pytest.mark.parametrize('status', sorted(set(S) - {S.REQUESTED}))
@pytest.mark.parametrize('action', ['counter', 'accept', 'reject'])
def test_negotiation_only_while_requested(api_client, item, lender, borrower, status, action):
    order = booking(item, at(10), at(13), borrower=borrower, status=status)
    # Leave a pending offer from the borrower so only the status check can fail.
    Offer.objects.create(order=order, proposed_by=borrower, hourly_rate=Decimal('40.00'))
    before = snapshot(order)

    response = act(api_client, lender, order, action, {'hourly_rate': '50.00'})

    assert response.status_code == 400
    assert 'no longer open for negotiation' in response.data['detail']
    assert snapshot(order) == before


@pytest.mark.parametrize('action', ['counter', 'accept', 'reject'])
def test_negotiation_needs_a_pending_offer(api_client, item, lender, action):
    order = booking(item, at(10), at(13), offer=False)

    response = act(api_client, lender, order, action, {'hourly_rate': '50.00'})

    assert response.status_code == 400
    assert 'No pending offer' in response.data['detail']


@pytest.mark.parametrize('action', ['counter', 'accept', 'reject'])
def test_stranger_cannot_negotiate(api_client, item, action):
    order = booking(item, at(10), at(13))
    stranger = UserFactory()
    before = snapshot(order)

    # The API hides other people's orders entirely...
    assert act(api_client, stranger, order, action, {'hourly_rate': '1.00'}).status_code == 404
    # ...and the service refuses them too, in case it's called from elsewhere.
    func = {'counter': services.counter_offer, 'accept': services.accept_offer,
            'reject': services.reject_offer}[action]
    kwargs = {'hourly_rate': Decimal('1.00')} if action == 'counter' else {}
    with pytest.raises(services.OrderError, match='not part of this order'):
        func(order, stranger, **kwargs)
    assert snapshot(order) == before


def test_stranger_has_no_role_or_actions(item):
    order = booking(item, at(10), at(13))
    stranger = UserFactory()

    assert services.role_of(order, stranger) is None
    assert services.allowed_actions(order, stranger) == []


# --- accept auto-rejects clashing requests ----------------------------------

def test_accept_rejects_clashing_requests_only(api_client, item, lender):
    accepted = booking(item, at(10), at(13))
    clash_start = booking(item, at(8), at(11))
    clash_end = booking(item, at(12), at(14))
    clash_inside = booking(item, at(11), at(12))
    touching_before = booking(item, at(8), at(10))
    touching_after = booking(item, at(13), at(15))
    other_item = booking(ItemFactory(), at(10), at(13))
    already_cancelled = booking(item, at(10), at(13), status=S.CANCELLED, offer=False)
    clashing = [clash_start, clash_end, clash_inside]
    untouched = [touching_before, touching_after, other_item]

    response = act(api_client, lender, accepted, 'accept')

    assert response.status_code == 200, response.data
    for order in clashing:
        order.refresh_from_db()
        assert order.status == S.REJECTED, order
        assert order.offers.get().status == O.REJECTED
    for order in untouched:
        order.refresh_from_db()
        assert order.status == S.REQUESTED, order
        assert order.offers.get().status == O.PENDING
    already_cancelled.refresh_from_db()
    assert already_cancelled.status == S.CANCELLED


def test_auto_reject_keeps_negotiation_history(api_client, item, lender):
    winner = booking(item, at(10), at(13))
    loser = booking(item, at(11), at(12))
    act(api_client, lender, loser, 'counter', {'hourly_rate': '70.00'})

    act(api_client, lender, winner, 'accept')

    assert [status for _, _, status in offers(loser)] == [O.COUNTERED, O.REJECTED]
    # The losing borrower can no longer respond.
    response = act(api_client, loser.borrower, loser, 'accept')
    assert response.status_code == 400
    assert 'no longer open' in response.data['detail']


def test_accept_refused_when_item_already_booked(api_client, item, lender):
    # e.g. a booking created outside the API, or left over from before auto-reject existed.
    booking(item, at(9), at(11), status=S.ACCEPTED, offer=False)
    order = booking(item, at(10), at(13))
    before = snapshot(order)

    response = act(api_client, lender, order, 'accept')

    assert response.status_code == 400
    assert 'already booked' in response.data['detail']
    assert snapshot(order) == before


def test_failed_accept_rolls_back_everything(api_client, item, lender, monkeypatch):
    order = booking(item, at(10), at(13))
    clash = booking(item, at(11), at(12))
    before = snapshot(order), snapshot(clash)

    def boom(self, *args, **kwargs):
        raise RuntimeError('db went away')

    monkeypatch.setattr(Order, 'transition_to', boom)
    with pytest.raises(RuntimeError):
        services.accept_offer(order, lender)

    assert (snapshot(order), snapshot(clash)) == before


# --- concurrency (real transactions, two connections) -----------------------

@pytest.mark.django_db(transaction=True)
def test_concurrent_accepts_of_clashing_requests_book_the_item_once():
    item = ItemFactory()
    first = booking(item, at(10), at(13))
    second = booking(item, at(11), at(14))
    barrier = threading.Barrier(2, timeout=10)
    results = {}

    def accept(order):
        try:
            barrier.wait()
            services.accept_offer(order, item.owner)
            results[order.pk] = 'accepted'
        except Exception as error:  # recorded, not raised: threads swallow exceptions
            results[order.pk] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=accept, args=(order,)) for order in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), 'accept_offer hung'

    # Exactly one wins. The loser must wait for the winner's lock and then fail
    # cleanly; without select_for_update the two transactions instead deadlock on
    # each other's order rows and Postgres aborts one with a DeadlockDetected error.
    outcomes = sorted(results.values(), key=lambda r: r != 'accepted')
    assert len(outcomes) == 2 and outcomes[0] == 'accepted', results
    loser = outcomes[1]
    assert isinstance(loser, services.OrderError), repr(loser)
    assert 'no longer open for negotiation' in str(loser)
    statuses = sorted(Order.objects.filter(item=item).values_list('status', flat=True))
    assert statuses == sorted([S.ACCEPTED, S.REJECTED])
    assert Offer.objects.filter(order__item=item, status=O.PENDING).count() == 0
