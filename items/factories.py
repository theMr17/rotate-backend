from decimal import Decimal

import factory

from items.models import Item
from user.factories import UserFactory


class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    owner = factory.SubFactory(UserFactory)
    title = factory.Faker('sentence', nb_words=3)
    description = factory.Faker('paragraph')
    category = 'Tools'
    hourly_rate = Decimal('50.00')
    deposit_amount = Decimal('500.00')
