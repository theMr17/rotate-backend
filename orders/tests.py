from datetime import timedelta
from decimal import Decimal
from itertools import count

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from items.models import Item
from .models import Offer, Order

User = get_user_model()
S = Order.Status
_seq = count()


def make_user(name):
    n = next(_seq)
    return User.objects.create_user(email=f'{name}{n}@example.com', password='pw', name=name)


def make_item(owner, **kwargs):
    defaults = dict(title='Drill', hourly_rate=Decimal('50.00'), deposit_amount=Decimal('500.00'))
    defaults.update(kwargs)
    return Item.objects.create(owner=owner, **defaults)


# action name -> (statuses it may be called from, roles allowed, resulting status)
LIFECYCLE = {
    'cancel': ({S.REQUESTED, S.ACCEPTED}, {'borrower', 'lender'}, S.CANCELLED),
    'start': ({S.ACCEPTED}, {'lender'}, S.ACTIVE),
    'return': ({S.ACTIVE}, {'borrower'}, S.RETURNED),
    'complete': ({S.RETURNED}, {'lender'}, S.COMPLETED),
    'dispute': ({S.RETURNED}, {'borrower', 'lender'}, S.DISPUTED),
}


class OrderTestBase(APITestCase):
    def setUp(self):
        self.lender = make_user('lender')
        self.borrower = make_user('borrower')
        self.stranger = make_user('stranger')
        self.item = make_item(self.lender)

    def make_order(self, status=S.REQUESTED):
        start = timezone.now() + timedelta(days=1)
        order = Order.objects.create(
            item=self.item, borrower=self.borrower, lender=self.lender,
            start_time=start, end_time=start + timedelta(hours=3), status=status,
            agreed_hourly_rate=None if status == S.REQUESTED else Decimal('40.00'),
        )
        if status == S.REQUESTED:
            Offer.objects.create(order=order, proposed_by=self.borrower, hourly_rate=Decimal('40.00'))
        return order

    def user_for(self, role):
        return {'borrower': self.borrower, 'lender': self.lender, 'stranger': self.stranger}[role]

    def post(self, user, url, data=None):
        self.client.force_authenticate(user)
        return self.client.post(url, data or {}, format='json')

    def act(self, order, action, role):
        return self.post(self.user_for(role), f'/api/v1/orders/{order.pk}/{action}/')


class HappyPathTests(OrderTestBase):
    def test_full_rental_loop_through_api(self):
        start = timezone.now() + timedelta(days=1)
        response = self.post(self.borrower, '/api/v1/orders/', {
            'item': self.item.pk,
            'start_time': start.isoformat(),
            'end_time': (start + timedelta(hours=2)).isoformat(),
            'hourly_rate': '45.00',
        })
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data['id'])
        self.assertEqual(order.status, S.REQUESTED)

        steps = [('accept', 'lender', S.ACCEPTED), ('start', 'lender', S.ACTIVE),
                 ('return', 'borrower', S.RETURNED), ('complete', 'lender', S.COMPLETED)]
        for action, role, expected in steps:
            response = self.act(order, action, role)
            self.assertEqual(response.status_code, 200, (action, response.data))
            self.assertEqual(response.data['status'], expected)

        order.refresh_from_db()
        self.assertEqual(order.status, S.COMPLETED)
        self.assertEqual(order.agreed_hourly_rate, Decimal('45.00'))
        self.assertIsNotNone(order.started_at)
        self.assertIsNotNone(order.returned_at)
        self.assertIsNotNone(order.completed_at)
        self.assertLessEqual(order.started_at, order.returned_at)
        self.assertLessEqual(order.returned_at, order.completed_at)
        self.assertIsNone(order.cancelled_by)


class AllowedTransitionTests(OrderTestBase):
    def test_every_allowed_transition_by_every_allowed_role(self):
        for action, (from_statuses, roles, to_status) in LIFECYCLE.items():
            for from_status in from_statuses:
                for role in roles:
                    with self.subTest(action=action, from_status=from_status, role=role):
                        order = self.make_order(from_status)
                        response = self.act(order, action, role)
                        self.assertEqual(response.status_code, 200, response.data)
                        order.refresh_from_db()
                        self.assertEqual(order.status, to_status)

    def test_timestamps_are_recorded(self):
        order = self.make_order(S.ACCEPTED)
        self.act(order, 'start', 'lender')
        order.refresh_from_db()
        self.assertIsNotNone(order.started_at)
        self.assertIsNone(order.returned_at)

        self.act(order, 'return', 'borrower')
        order.refresh_from_db()
        self.assertIsNotNone(order.returned_at)
        self.assertIsNone(order.completed_at)

        response = self.act(order, 'complete', 'lender')
        order.refresh_from_db()
        self.assertIsNotNone(order.completed_at)
        self.assertIsNotNone(response.data['completed_at'])

    def test_cancel_records_who_cancelled(self):
        for role in ('borrower', 'lender'):
            with self.subTest(role=role):
                order = self.make_order(S.ACCEPTED)
                response = self.act(order, 'cancel', role)
                order.refresh_from_db()
                self.assertEqual(order.cancelled_by, self.user_for(role))
                self.assertEqual(response.data['cancelled_by'], self.user_for(role).id)

    def test_cancel_closes_pending_offer(self):
        order = self.make_order(S.REQUESTED)
        self.act(order, 'cancel', 'borrower')
        self.assertFalse(order.offers.filter(status=Offer.Status.PENDING).exists())

    def test_dispute_does_not_set_completed_at(self):
        order = self.make_order(S.RETURNED)
        self.act(order, 'dispute', 'borrower')
        order.refresh_from_db()
        self.assertEqual(order.status, S.DISPUTED)
        self.assertIsNone(order.completed_at)


class ForbiddenTransitionTests(OrderTestBase):
    def test_every_forbidden_transition_returns_400_and_keeps_state(self):
        for action, (from_statuses, roles, _) in LIFECYCLE.items():
            for status in set(S) - from_statuses:
                for role in roles:
                    with self.subTest(action=action, status=status, role=role):
                        order = self.make_order(status)
                        before = Order.objects.filter(pk=order.pk).values().get()
                        response = self.act(order, action, role)
                        self.assertEqual(response.status_code, 400, response.data)
                        self.assertIn('detail', response.data)
                        self.assertEqual(Order.objects.filter(pk=order.pk).values().get(), before)

    def test_disputed_order_cannot_be_completed_by_lender(self):
        order = self.make_order(S.DISPUTED)
        response = self.act(order, 'complete', 'lender')
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, S.DISPUTED)


class WrongRoleTests(OrderTestBase):
    def test_wrong_party_gets_403_and_state_is_unchanged(self):
        for action, (from_statuses, roles, _) in LIFECYCLE.items():
            for role in {'borrower', 'lender'} - roles:
                for status in from_statuses:
                    with self.subTest(action=action, role=role, status=status):
                        order = self.make_order(status)
                        before = Order.objects.filter(pk=order.pk).values().get()
                        response = self.act(order, action, role)
                        self.assertEqual(response.status_code, 403, response.data)
                        self.assertIn('Only the', str(response.data['detail']))
                        self.assertEqual(Order.objects.filter(pk=order.pk).values().get(), before)

    def test_stranger_cannot_see_or_act_on_order(self):
        for action, (from_statuses, _, _) in LIFECYCLE.items():
            with self.subTest(action=action):
                order = self.make_order(next(iter(from_statuses)))
                response = self.act(order, action, 'stranger')
                self.assertEqual(response.status_code, 404)
                order.refresh_from_db()
                self.assertIn(order.status, from_statuses)

    def test_unauthenticated_is_rejected(self):
        order = self.make_order(S.ACCEPTED)
        response = self.client.post(f'/api/v1/orders/{order.pk}/start/')
        self.assertEqual(response.status_code, 401)


class ItemAvailabilityTests(OrderTestBase):
    def test_request_rejected_when_item_unavailable(self):
        self.item.status = 'UNAVAILABLE'
        self.item.save()
        start = timezone.now() + timedelta(days=1)
        response = self.post(self.borrower, '/api/v1/orders/', {
            'item': self.item.pk,
            'start_time': start.isoformat(),
            'end_time': (start + timedelta(hours=2)).isoformat(),
            'hourly_rate': '45.00',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_accept_rejected_when_item_became_unavailable(self):
        order = self.make_order(S.REQUESTED)
        self.item.status = 'UNAVAILABLE'
        self.item.save()
        response = self.act(order, 'accept', 'lender')
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, S.REQUESTED)
        self.assertIsNone(order.agreed_hourly_rate)
        self.assertTrue(order.offers.filter(status=Offer.Status.PENDING).exists())
