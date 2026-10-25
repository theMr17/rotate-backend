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
    cancelled_by = serializers.StringRelatedField()
    offers = OfferSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'booking_ref', 'item', 'item_title', 'borrower', 'lender', 'start_time', 'end_time',
            'status', 'agreed_hourly_rate', 'rental_fee', 'platform_fee', 'deposit_amount',
            'total_due', 'offers',
            'started_at', 'returned_at', 'completed_at', 'cancelled_by',
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


class QuoteQuerySerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01'), required=False
    )

    def validate(self, attrs):
        if attrs['end'] <= attrs['start']:
            raise serializers.ValidationError({'end': 'End time must be after start time.'})
        return attrs


class PriceBreakdownSerializer(serializers.Serializer):
    billable_hours = serializers.IntegerField()
    hourly_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    rental_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    deposit = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_due = serializers.DecimalField(max_digits=12, decimal_places=2)
