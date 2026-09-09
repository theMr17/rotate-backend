from django.test import TestCase


class HealthCheckTests(TestCase):
	def test_health_check_returns_ok(self):
		response = self.client.get('/health/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.headers['Content-Type'], 'application/json')
		self.assertJSONEqual(response.content, {'status': 'ok'})

	def test_health_check_only_accepts_get(self):
		response = self.client.post('/health/')

		self.assertEqual(response.status_code, 405)
