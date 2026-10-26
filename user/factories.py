import factory
from django.contrib.auth import get_user_model

DEFAULT_PASSWORD = 'strong-password-123'


class UserFactory(factory.django.DjangoModelFactory):
	class Meta:
		model = get_user_model()

	name = factory.Faker('name')
	email = factory.Sequence(lambda n: f'user{n}@example.com')
	password = factory.django.Password(DEFAULT_PASSWORD)
