import json
from decimal import Decimal

from .models import Offer, Order
from .services import LIFECYCLE_RULES
from .tests import LIFECYCLE, OrderTestBase

S = Order.Status
REVEALED = {S.ACCEPTED, S.ACTIVE, S.RETURNED, S.DISPUTED, S.COMPLETED}


class ContactPrivacyTests(OrderTestBase):
    def setUp(self):
        super().setUp()
        self.lender.phone = '+91 98765 43210'
        self.lender.location = '12 MG Road, Pune'
        self.lender.save()

    def get(self, order, role):
        self.client.force_authenticate(self.user_for(role))
        response = self.client.get(f'/api/v1/orders/{order.pk}/')
        self.assertEqual(response.status_code, 200)
        return response

    def test_borrower_cannot_see_lender_email_on_requested_order(self):
        order = self.make_order(S.REQUESTED)
        response = self.get(order, 'borrower')
        self.assertIsNone(response.data['lender']['contact'])
        body = json.dumps(response.data, default=str)
        for secret in (self.lender.email, self.lender.phone, self.lender.location,
                       self.borrower.email):
            self.assertNotIn(secret, body)

    def test_contact_hidden_until_accepted(self):
        for status in S:
            for viewer, other in (('borrower', 'lender'), ('lender', 'borrower')):
                with self.subTest(status=status, viewer=viewer):
                    order = self.make_order(status)
                    contact = self.get(order, viewer).data[other]['contact']
                    if status in REVEALED:
                        self.assertEqual(contact['email'], self.user_for(other).email)
                        self.assertEqual(set(contact), {'email', 'phone', 'location'})
                    else:
                        self.assertIsNone(contact)

    def test_contact_revealed_once_lender_accepts(self):
        order = self.make_order(S.REQUESTED)
        self.client.force_authenticate(self.lender)
        response = self.client.post(f'/api/v1/orders/{order.pk}/accept/')
        self.assertEqual(response.data['borrower']['contact']['email'], self.borrower.email)
        self.assertEqual(self.get(order, 'borrower').data['lender']['contact'], {
            'email': self.lender.email, 'phone': '+91 98765 43210', 'location': '12 MG Road, Pune',
        })

    def test_list_endpoint_hides_contact_too(self):
        self.make_order(S.REQUESTED)
        self.client.force_authenticate(self.borrower)
        body = json.dumps(self.client.get('/api/v1/orders/').data, default=str)
        self.assertNotIn(self.lender.email, body)

    def test_participant_and_item_shape(self):
        order = self.make_order(S.REQUESTED)
        data = self.get(order, 'borrower').data
        self.assertEqual(data['lender'], {
            'id': self.lender.id, 'name': self.lender.name,
            'avatar': None, 'reliability_score': None, 'contact': None,
        })
        self.assertEqual(data['item'], {
            'id': self.item.id, 'title': self.item.title,
            'cover_photo': None, 'owner': self.lender.id,
        })
        self.assertEqual(data['offers'][0]['proposed_by'], self.borrower.id)


class MyRoleAndAllowedActionsTests(OrderTestBase):
    def data(self, order, role):
        self.client.force_authenticate(self.user_for(role))
        return self.client.get(f'/api/v1/orders/{order.pk}/').data

    def test_my_role(self):
        order = self.make_order()
        self.assertEqual(self.data(order, 'borrower')['my_role'], 'borrower')
        self.assertEqual(self.data(order, 'lender')['my_role'], 'lender')

    def test_requested_order_actions_depend_on_whose_turn(self):
        order = self.make_order(S.REQUESTED)  # borrower made the opening offer
        self.assertEqual(self.data(order, 'borrower')['allowed_actions'], ['cancel'])
        self.assertEqual(self.data(order, 'lender')['allowed_actions'],
                         ['accept', 'counter', 'reject', 'cancel'])

        self.client.force_authenticate(self.lender)
        self.client.post(f'/api/v1/orders/{order.pk}/counter/', {'hourly_rate': '45.00'}, format='json')
        self.assertEqual(self.data(order, 'borrower')['allowed_actions'],
                         ['accept', 'counter', 'reject', 'cancel'])
        self.assertEqual(self.data(order, 'lender')['allowed_actions'], ['cancel'])

    def test_accept_hidden_when_item_unavailable(self):
        order = self.make_order(S.REQUESTED)
        self.item.status = 'UNAVAILABLE'
        self.item.save()
        self.assertEqual(self.data(order, 'lender')['allowed_actions'], ['counter', 'reject', 'cancel'])

    def test_lifecycle_actions_per_status(self):
        expected = {
            S.ACCEPTED: {'borrower': ['cancel'], 'lender': ['cancel', 'start']},
            S.ACTIVE: {'borrower': ['return'], 'lender': []},
            S.RETURNED: {'borrower': ['dispute'], 'lender': ['complete', 'dispute']},
            S.DISPUTED: {'borrower': [], 'lender': []},
            S.COMPLETED: {'borrower': [], 'lender': []},
            S.REJECTED: {'borrower': [], 'lender': []},
            S.CANCELLED: {'borrower': [], 'lender': []},
        }
        for status, by_role in expected.items():
            order = self.make_order(status)
            for role, actions in by_role.items():
                with self.subTest(status=status, role=role):
                    self.assertEqual(self.data(order, role)['allowed_actions'], actions)

    def test_every_advertised_action_succeeds_and_no_other_does(self):
        """allowed_actions must agree exactly with what the API accepts."""
        for status in S:
            for role in ('borrower', 'lender'):
                order = self.make_order(status)
                advertised = set(self.data(order, role)['allowed_actions'])
                for action in ['accept', 'reject', *LIFECYCLE]:
                    with self.subTest(status=status, role=role, action=action):
                        fresh = self.make_order(status)
                        code = self.act(fresh, action, role).status_code
                        if action in advertised:
                            self.assertEqual(code, 200)
                        else:
                            self.assertIn(code, (400, 403))
                    Order.objects.filter(item=self.item).update(status=S.CANCELLED)

    def test_rules_table_matches_test_matrix(self):
        for action, (statuses, roles, _) in LIFECYCLE.items():
            rule_roles, rule_statuses = LIFECYCLE_RULES[action]
            self.assertEqual(set(rule_roles), roles)
            self.assertEqual(set(rule_statuses), statuses)


class ListFilterTests(OrderTestBase):
    def ids(self, user, **params):
        self.client.force_authenticate(user)
        response = self.client.get('/api/v1/orders/', params)
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id'] for row in response.data}

    def test_status_filter(self):
        requested = self.make_order(S.REQUESTED)
        accepted = self.make_order(S.ACCEPTED)
        active = self.make_order(S.ACTIVE)
        self.assertEqual(self.ids(self.borrower, status='accepted'), {accepted.id})
        self.assertEqual(self.ids(self.borrower, status='accepted,active'), {accepted.id, active.id})
        self.assertEqual(self.ids(self.borrower), {requested.id, accepted.id, active.id})

    def test_unknown_status_is_400(self):
        self.client.force_authenticate(self.borrower)
        response = self.client.get('/api/v1/orders/', {'status': 'accepted,bogus'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('bogus', str(response.data['status']))

    def test_needs_action(self):
        waiting_on_lender = self.make_order(S.REQUESTED)  # borrower's offer pending
        waiting_on_borrower = self.make_order(S.REQUESTED)
        waiting_on_borrower.offers.update(status=Offer.Status.COUNTERED)
        Offer.objects.create(order=waiting_on_borrower, proposed_by=self.lender, hourly_rate=Decimal('45'))
        self.make_order(S.ACCEPTED)

        self.assertEqual(self.ids(self.lender, needs_action='true'), {waiting_on_lender.id})
        self.assertEqual(self.ids(self.borrower, needs_action='true'), {waiting_on_borrower.id})
        self.assertEqual(len(self.ids(self.borrower, needs_action='false')), 3)

    def test_needs_action_combines_with_role(self):
        self.make_order(S.REQUESTED)
        self.assertEqual(self.ids(self.lender, needs_action='true', role='borrower'), set())

    def test_bad_needs_action_is_400(self):
        self.client.force_authenticate(self.borrower)
        self.assertEqual(self.client.get('/api/v1/orders/', {'needs_action': 'maybe'}).status_code, 400)

    def test_filters_do_not_affect_detail_actions(self):
        order = self.make_order(S.ACCEPTED)
        self.client.force_authenticate(self.lender)
        response = self.client.post(f'/api/v1/orders/{order.pk}/start/?status=requested')
        self.assertEqual(response.status_code, 200)

    def test_list_query_count_is_constant(self):
        for _ in range(5):
            self.make_order(S.REQUESTED)
        self.client.force_authenticate(self.lender)
        with self.assertNumQueries(2):  # orders + prefetched offers
            self.client.get('/api/v1/orders/')
