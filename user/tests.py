import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .factories import DEFAULT_PASSWORD

User = get_user_model()

pytestmark = pytest.mark.django_db


def login(client, user, password=DEFAULT_PASSWORD):
	return client.post(reverse('login'), {'email': user.email, 'password': password}, format='json')


def test_register_hashes_password_and_returns_tokens(api_client):
	response = api_client.post(reverse('register'), {
		'name': 'Test User',
		'email': 'test@example.com',
		'password': 'strong-password-123',
		'phone': '+15555555555',
		'location': 'Remote',
	}, format='json')

	assert response.status_code == 201
	assert {'access', 'refresh'} <= set(response.data)
	user = User.objects.get(email='test@example.com')
	assert user.check_password('strong-password-123')
	assert user.password != 'strong-password-123'


def test_register_rejects_duplicate_email(api_client, user):
	response = api_client.post(reverse('register'), {
		'name': 'Someone Else',
		'email': user.email,
		'password': 'another-password-456',
	}, format='json')

	assert response.status_code == 400
	assert User.objects.filter(email=user.email).count() == 1


def test_login_returns_tokens_for_valid_password(api_client, user):
	response = login(api_client, user)

	assert response.status_code == 200
	assert {'access', 'refresh'} <= set(response.data)


def test_login_rejects_invalid_password(api_client, user):
	response = login(api_client, user, password='wrong-password')

	assert response.status_code == 400


def test_logout_blacklists_refresh_token(api_client, user):
	refresh = login(api_client, user).data['refresh']

	response = api_client.post(reverse('logout'), {'refresh': refresh}, format='json')

	assert response.status_code == 204
	refresh_response = api_client.post(reverse('token-refresh'), {'refresh': refresh}, format='json')
	assert refresh_response.status_code == 401


def test_logout_requires_refresh_token(api_client):
	response = api_client.post(reverse('logout'), {}, format='json')

	assert response.status_code == 400


def test_token_refresh_returns_new_access_token(api_client, user):
	refresh = login(api_client, user).data['refresh']

	response = api_client.post(reverse('token-refresh'), {'refresh': refresh}, format='json')

	assert response.status_code == 200
	assert 'access' in response.data


def test_profile_returns_current_user(auth_client):
	response = auth_client.get(reverse('profile'))

	assert response.status_code == 200
	assert response.data['email'] == auth_client.user.email
	assert 'password' not in response.data


def test_profile_requires_authentication(api_client):
	response = api_client.get(reverse('profile'))

	assert response.status_code == 401
