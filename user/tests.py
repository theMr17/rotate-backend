from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()


class AuthenticationTests(APITestCase):
	def test_register_hashes_password_and_returns_tokens(self):
		response = self.client.post('/api/v1/register', {
			'name': 'Test User',
			'email': 'test@example.com',
			'password': 'strong-password-123',
			'phone': '+15555555555',
			'location': 'Remote',
		}, format='json')

		self.assertEqual(response.status_code, 201)
		self.assertIn('access', response.data)
		self.assertIn('refresh', response.data)
		user = User.objects.get(email='test@example.com')
		self.assertTrue(user.check_password('strong-password-123'))
		self.assertNotEqual(user.password, 'strong-password-123')

	def test_login_returns_tokens_for_valid_password(self):
		User.objects.create_user('test@example.com', 'strong-password-123', name='Test User')

		response = self.client.post('/api/v1/login', {
			'email': 'test@example.com',
			'password': 'strong-password-123',
		}, format='json')

		self.assertEqual(response.status_code, 200)
		self.assertIn('access', response.data)
		self.assertIn('refresh', response.data)

	def test_login_rejects_invalid_password(self):
		User.objects.create_user('test@example.com', 'strong-password-123', name='Test User')

		response = self.client.post('/api/v1/login', {
			'email': 'test@example.com',
			'password': 'wrong-password',
		}, format='json')

		self.assertEqual(response.status_code, 400)

	def test_logout_blacklists_refresh_token(self):
		user = User.objects.create_user('test@example.com', 'strong-password-123', name='Test User')
		login_response = self.client.post('/api/v1/login', {
			'email': 'test@example.com',
			'password': 'strong-password-123',
		}, format='json')

		response = self.client.post('/api/v1/logout', {
			'refresh': login_response.data['refresh'],
		}, format='json')

		self.assertEqual(response.status_code, 204)
		refresh_response = self.client.post('/api/v1/token/refresh', {
			'refresh': login_response.data['refresh'],
		}, format='json')
		self.assertEqual(refresh_response.status_code, 401)

	def test_logout_requires_refresh_token(self):
		response = self.client.post('/api/v1/logout', {}, format='json')

		self.assertEqual(response.status_code, 400)
