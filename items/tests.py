from decimal import Decimal

import pytest
from django.urls import reverse

from items.factories import ItemFactory
from items.models import Item
from orders.factories import OrderFactory
from orders.models import Order
from user.factories import UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse('item-list')


def detail_url(item):
    return reverse('item-detail', args=[item.pk])


def ids(response):
    assert response.status_code == 200, response.data
    return {row['id'] for row in response.data}


def as_user(api_client, user):
    api_client.force_authenticate(user)
    return api_client


# --- list -------------------------------------------------------------------

def test_list_is_public_and_shows_only_available_items(api_client):
    available = ItemFactory()
    ItemFactory(status='UNAVAILABLE')

    assert ids(api_client.get(LIST_URL)) == {available.pk}


def test_mine_returns_all_my_items_including_unavailable(api_client, user):
    mine = {ItemFactory(owner=user).pk, ItemFactory(owner=user, status='UNAVAILABLE').pk}
    ItemFactory()

    assert ids(as_user(api_client, user).get(LIST_URL, {'mine': 'true'})) == mine


def test_mine_is_case_insensitive_and_other_values_mean_catalogue(api_client, user):
    hidden = ItemFactory(owner=user, status='UNAVAILABLE')
    other = ItemFactory()
    client = as_user(api_client, user)

    assert hidden.pk in ids(client.get(LIST_URL, {'mine': 'TRUE'}))
    assert ids(client.get(LIST_URL, {'mine': 'false'})) == {other.pk}


def test_mine_requires_authentication(api_client):
    response = api_client.get(LIST_URL, {'mine': 'true'})

    assert response.status_code == 401


def test_category_filter_is_case_insensitive_exact_match(api_client):
    camera = ItemFactory(category='Electronics')
    ItemFactory(category='Electronics Accessories')
    ItemFactory(category='Tools')

    assert ids(api_client.get(LIST_URL, {'category': 'electronics'})) == {camera.pk}


def test_search_matches_title_or_description(api_client):
    by_title = ItemFactory(title='Canon DSLR Camera', description='Great kit')
    by_description = ItemFactory(title='Lens bundle', description='Fits any CAMERA body')
    ItemFactory(title='Cordless drill', description='18V')

    assert ids(api_client.get(LIST_URL, {'search': 'camera'})) == {by_title.pk, by_description.pk}


def test_filters_combine_with_each_other_and_with_mine(api_client, user):
    match = ItemFactory(owner=user, category='Tools', title='Drill', status='UNAVAILABLE')
    ItemFactory(owner=user, category='Tools', title='Saw')
    ItemFactory(owner=user, category='Garden', title='Drill')
    ItemFactory(category='Tools', title='Drill')

    response = as_user(api_client, user).get(
        LIST_URL, {'mine': 'true', 'category': 'tools', 'search': 'drill'}
    )
    assert ids(response) == {match.pk}


# --- create -----------------------------------------------------------------

def test_create_sets_owner_from_request_user(api_client, user):
    someone_else = UserFactory()

    response = as_user(api_client, user).post(LIST_URL, {
        'title': 'Tent', 'hourly_rate': '25.00', 'owner': someone_else.pk,
    }, format='json')

    assert response.status_code == 201, response.data
    item = Item.objects.get(pk=response.data['id'])
    assert item.owner == user
    assert item.deposit_amount == Decimal('0.00')
    assert (item.status, item.condition, item.category) == ('AVAILABLE', 'GOOD', 'Other')


def test_create_requires_authentication(api_client):
    response = api_client.post(LIST_URL, {'title': 'Tent', 'hourly_rate': '25.00'}, format='json')

    assert response.status_code == 401
    assert not Item.objects.exists()


@pytest.mark.parametrize('payload, field', [
    ({'title': 'Tent', 'hourly_rate': '0.00'}, 'hourly_rate'),
    ({'title': 'Tent', 'hourly_rate': '10.00', 'deposit_amount': '-1.00'}, 'deposit_amount'),
    ({'title': 'Tent', 'hourly_rate': '10.00', 'condition': 'MINT'}, 'condition'),
    ({'title': 'Tent', 'hourly_rate': '10.00', 'status': 'GONE'}, 'status'),
    ({'hourly_rate': '10.00'}, 'title'),
])
def test_create_validation(api_client, user, payload, field):
    response = as_user(api_client, user).post(LIST_URL, payload, format='json')

    assert response.status_code == 400
    assert field in response.data
    assert not Item.objects.exists()


# --- retrieve ---------------------------------------------------------------

def test_detail_is_public_even_when_unavailable(api_client):
    item = ItemFactory(status='UNAVAILABLE')

    response = api_client.get(detail_url(item))

    assert response.status_code == 200
    assert response.data['id'] == item.pk
    assert response.data['owner'] == item.owner_id


@pytest.mark.parametrize('method', ['get', 'patch', 'delete'])
def test_unknown_item_is_404(api_client, user, method):
    response = getattr(as_user(api_client, user), method)(reverse('item-detail', args=[999999]))

    assert response.status_code == 404


# --- update -----------------------------------------------------------------

def test_owner_can_patch_and_owner_field_is_read_only(api_client):
    item = ItemFactory(hourly_rate=Decimal('50.00'))
    someone_else = UserFactory()

    response = as_user(api_client, item.owner).patch(detail_url(item), {
        'hourly_rate': '60.00', 'status': 'UNAVAILABLE', 'owner': someone_else.pk,
    }, format='json')

    assert response.status_code == 200, response.data
    item.refresh_from_db()
    assert item.hourly_rate == Decimal('60.00')
    assert item.status == 'UNAVAILABLE'
    assert item.owner != someone_else


def test_owner_patch_is_validated(api_client):
    item = ItemFactory()

    response = as_user(api_client, item.owner).patch(
        detail_url(item), {'hourly_rate': '-5'}, format='json'
    )

    assert response.status_code == 400
    item.refresh_from_db()
    assert item.hourly_rate == Decimal('50.00')


def test_non_owner_cannot_patch(api_client, user):
    item = ItemFactory(title='Original')

    response = as_user(api_client, user).patch(detail_url(item), {'title': 'Hijacked'}, format='json')

    assert response.status_code == 403
    item.refresh_from_db()
    assert item.title == 'Original'


@pytest.mark.parametrize('method', ['patch', 'delete'])
def test_anonymous_cannot_modify(api_client, method):
    item = ItemFactory(title='Original')

    response = getattr(api_client, method)(detail_url(item), {'title': 'x'}, format='json')

    assert response.status_code == 401
    item.refresh_from_db()
    assert item.title == 'Original'


# --- delete -----------------------------------------------------------------

def test_owner_can_delete_item_without_orders(api_client):
    item = ItemFactory()

    response = as_user(api_client, item.owner).delete(detail_url(item))

    assert response.status_code == 204
    assert not Item.objects.filter(pk=item.pk).exists()


def test_non_owner_cannot_delete(api_client, user):
    item = ItemFactory()

    response = as_user(api_client, user).delete(detail_url(item))

    assert response.status_code == 403
    assert Item.objects.filter(pk=item.pk).exists()


@pytest.mark.parametrize('status', [Order.Status.REQUESTED, Order.Status.COMPLETED])
def test_delete_with_orders_is_409_and_keeps_item(api_client, status):
    order = OrderFactory(status=status)
    item = order.item

    response = as_user(api_client, item.owner).delete(detail_url(item))

    assert response.status_code == 409
    assert 'UNAVAILABLE' in response.data['detail']
    assert Item.objects.filter(pk=item.pk).exists()
    assert Order.objects.filter(pk=order.pk).exists()
