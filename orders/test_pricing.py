from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from unittest import mock

from django.db import transaction
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from . import pricing
from .models import (
    BOOKING_REF_ALPHABET, BOOKING_REF_PREFIX, BookingRefUnavailable, Order, generate_booking_ref,
)
from .tests import make_item, make_user

T0 = datetime(2026, 12, 1, 10, 0, tzinfo=dt_timezone.utc)


@override_settings(PLATFORM_FEE_PERCENT=Decimal('10'))
class PricingUnitTests(SimpleTestCase):
    def test_billable_hours_rounds_partial_hours_up(self):
        cases = [
            (timedelta(minutes=1), 1),
            (timedelta(minutes=59), 1),
            (timedelta(hours=1), 1),
            (timedelta(hours=1, seconds=1), 2),
            (timedelta(hours=2, minutes=30), 3),
            (timedelta(days=1), 24),
        ]
        for duration, expected in cases:
            with self.subTest(duration=duration):
                self.assertEqual(pricing.billable_hours(T0, T0 + duration), expected)

    def test_billable_hours_rejects_empty_or_negative_period(self):
        for end in (T0, T0 - timedelta(hours=1)):
            with self.subTest(end=end), self.assertRaises(ValueError):
                pricing.billable_hours(T0, end)

    def test_breakdown_with_partial_hour(self):
        b = pricing.calculate(Decimal('50'), T0, T0 + timedelta(hours=2, minutes=10), Decimal('500'))
        self.assertEqual(b.billable_hours, 3)
        self.assertEqual(b.rental_fee, Decimal('150.00'))
        self.assertEqual(b.platform_fee, Decimal('15.00'))
        self.assertEqual(b.deposit, Decimal('500.00'))
        self.assertEqual(b.total_due, Decimal('665.00'))

    def test_breakdown_with_zero_deposit(self):
        for deposit in (Decimal('0'), None):
            with self.subTest(deposit=deposit):
                b = pricing.calculate(Decimal('40'), T0, T0 + timedelta(hours=2), deposit)
                self.assertEqual(b.deposit, Decimal('0.00'))
                self.assertEqual(b.total_due, b.rental_fee + b.platform_fee)
                self.assertEqual(b.total_due, Decimal('88.00'))

    def test_platform_fee_rounds_half_up_to_paise(self):
        # 1h at 33.33 -> fee 3.333 -> 3.33 ; 1h at 0.05 -> fee 0.005 -> 0.01
        self.assertEqual(pricing.calculate(Decimal('33.33'), T0, T0 + timedelta(hours=1)).platform_fee, Decimal('3.33'))
        self.assertEqual(pricing.calculate(Decimal('0.05'), T0, T0 + timedelta(hours=1)).platform_fee, Decimal('0.01'))

    def test_fee_percent_comes_from_settings(self):
        with self.settings(PLATFORM_FEE_PERCENT=Decimal('2.5')):
            b = pricing.calculate(Decimal('100'), T0, T0 + timedelta(hours=1))
        self.assertEqual(b.platform_fee_percent, Decimal('2.5'))
        self.assertEqual(b.platform_fee, Decimal('2.50'))
        self.assertEqual(b.total_due, Decimal('102.50'))

    def test_platform_fee_is_not_charged_on_deposit(self):
        b = pricing.calculate(Decimal('10'), T0, T0 + timedelta(hours=1), Decimal('1000'))
        self.assertEqual(b.platform_fee, Decimal('1.00'))


@override_settings(PLATFORM_FEE_PERCENT=Decimal('10'))
class QuoteEndpointTests(APITestCase):
    def setUp(self):
        self.lender = make_user('lender')
        self.borrower = make_user('borrower')
        self.item = make_item(self.lender, hourly_rate=Decimal('50.00'), deposit_amount=Decimal('500.00'))
        self.start = (timezone.now() + timedelta(days=1)).replace(microsecond=0)
        self.end = self.start + timedelta(hours=2, minutes=15)

    def quote(self, **params):
        params = {'start': self.start.isoformat(), 'end': self.end.isoformat(), **params}
        return self.client.get(f'/api/v1/items/{self.item.pk}/quote/', params)

    def test_quote_uses_item_rate_by_default_and_is_public(self):
        response = self.quote()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {
            'billable_hours': 3,
            'hourly_rate': '50.00',
            'rental_fee': '150.00',
            'platform_fee_percent': '10.00',
            'platform_fee': '15.00',
            'deposit': '500.00',
            'total_due': '665.00',
        })

    def test_quote_with_proposed_rate(self):
        response = self.quote(rate='40.00')
        self.assertEqual(response.data['rental_fee'], '120.00')
        self.assertEqual(response.data['total_due'], '632.00')

    def test_quote_validation(self):
        cases = [
            {'start': ''},
            {'end': self.start.isoformat()},
            {'end': (self.start - timedelta(hours=1)).isoformat()},
            {'rate': '0'},
            {'rate': 'abc'},
        ]
        for params in cases:
            with self.subTest(params=params):
                self.assertEqual(self.quote(**params).status_code, 400)

    def test_quote_unknown_item_404(self):
        response = self.client.get('/api/v1/items/999999/quote/', {
            'start': self.start.isoformat(), 'end': self.end.isoformat(),
        })
        self.assertEqual(response.status_code, 404)

    def test_quote_matches_accepted_order_snapshot(self):
        for deposit in (Decimal('500.00'), Decimal('0.00')):
            with self.subTest(deposit=deposit):
                self.item.deposit_amount = deposit
                self.item.save()
                quote = self.quote(rate='45.00').data

                self.client.force_authenticate(self.borrower)
                created = self.client.post('/api/v1/orders/', {
                    'item': self.item.pk, 'start_time': self.start.isoformat(),
                    'end_time': self.end.isoformat(), 'hourly_rate': '45.00',
                }, format='json')
                self.assertEqual(created.status_code, 201, created.data)
                self.assertIsNone(created.data['total_due'])

                self.client.force_authenticate(self.lender)
                accepted = self.client.post(f"/api/v1/orders/{created.data['id']}/accept/").data
                self.client.force_authenticate(None)

                self.assertEqual(accepted['status'], 'accepted')
                for field in ('rental_fee', 'platform_fee', 'total_due'):
                    self.assertEqual(accepted[field], quote[field], field)
                self.assertEqual(accepted['deposit_amount'], quote['deposit'])

                # free the slot for the next subTest
                Order.objects.filter(pk=created.data['id']).update(status=Order.Status.CANCELLED)


class BookingRefTests(APITestCase):
    def setUp(self):
        self.lender = make_user('lender')
        self.borrower = make_user('borrower')
        self.item = make_item(self.lender)

    def make_order(self, **kwargs):
        start = timezone.now() + timedelta(days=1)
        return Order.objects.create(
            item=self.item, borrower=self.borrower, lender=self.lender,
            start_time=start, end_time=start + timedelta(hours=1), **kwargs,
        )

    def test_ref_generated_on_create_and_stable(self):
        order = self.make_order()
        self.assertRegex(order.booking_ref, rf'^{BOOKING_REF_PREFIX}[{BOOKING_REF_ALPHABET}]{{6}}$')
        ref = order.booking_ref
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.booking_ref, ref)

    def test_ref_avoids_ambiguous_characters(self):
        refs = ''.join(generate_booking_ref()[len(BOOKING_REF_PREFIX):] for _ in range(2000))
        self.assertFalse(set(refs) & set('ILOU'))

    def test_ref_retries_on_collision(self):
        existing = self.make_order()
        refs = iter([existing.booking_ref, existing.booking_ref, 'ROT-7K3QX9'])
        with mock.patch('orders.models.generate_booking_ref', lambda: next(refs)):
            order = self.make_order()
        self.assertEqual(order.booking_ref, 'ROT-7K3QX9')
        self.assertEqual(Order.objects.count(), 2)

    def test_collision_inside_outer_transaction_does_not_break_it(self):
        existing = self.make_order()
        refs = iter([existing.booking_ref, 'ROT-AAAAAA'])
        with transaction.atomic(), mock.patch('orders.models.generate_booking_ref', lambda: next(refs)):
            order = self.make_order()
            Order.objects.count()  # would raise if the transaction were aborted
        self.assertEqual(order.booking_ref, 'ROT-AAAAAA')

    def test_gives_up_cleanly_when_every_attempt_collides(self):
        existing = self.make_order()
        with mock.patch('orders.models.generate_booking_ref', lambda: existing.booking_ref):
            with self.assertRaises(BookingRefUnavailable):
                self.make_order()
        self.assertEqual(Order.objects.count(), 1)

    def test_exhaustion_returns_400_not_500(self):
        existing = self.make_order(status=Order.Status.CANCELLED)
        self.client.force_authenticate(self.borrower)
        start = timezone.now() + timedelta(days=2)
        with mock.patch('orders.models.generate_booking_ref', lambda: existing.booking_ref):
            response = self.client.post('/api/v1/orders/', {
                'item': self.item.pk, 'start_time': start.isoformat(),
                'end_time': (start + timedelta(hours=1)).isoformat(), 'hourly_rate': '45.00',
            }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('booking reference', str(response.data['detail']))

    def test_ref_exposed_in_api(self):
        order = self.make_order()
        self.client.force_authenticate(self.borrower)
        response = self.client.get(f'/api/v1/orders/{order.pk}/')
        self.assertEqual(response.data['booking_ref'], order.booking_ref)
