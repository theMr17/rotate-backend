from rest_framework import serializers
from decimal import Decimal
from items.models import Item
from .models import *

class OfferSerializer(serializers.ModelSerializer):
    proposed_by = serializers.StringRelatedField()
    class Meta:
        model = Offer
        fields = ['id', 'proposed_by', 'hourly_rate', 'message', 'status', 'created_at']

class OrderSerializer(serializers.ModelSerializer):
    borrower = serializers.StringRelatedField()
    lender = serializers.StringRelatedField()
    item_title = serializers.CharField(source='item.title', read_only=True)
    offers = OfferSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'item', 'item_title', 'borrower', 'lender', 'start_time', 'end_time',
            'status', 'agreed_hourly_rate', 'deposit_amount', 'offers',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

class RentalRequestSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    hourly_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01')
    )
    message = serializers.CharField(required=False, allow_blank=True, default='')


class CounterOfferSerializer(serializers.Serializer):
    hourly_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01')
    )
    message = serializers.CharField(required=False, allow_blank=True, default='')