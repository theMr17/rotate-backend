from rest_framework import serializers
from decimal import Decimal
from items.models import Item
from .models import *
from . import services

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
    my_role = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'item', 'item_title', 'borrower', 'lender', 'start_time', 'end_time',
            'status', 'agreed_hourly_rate', 'deposit_amount', 'offers',
            'my_role', 'available_actions', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_my_role(self, order):
        user = self.context['request'].user
        return 'lender' if order.lender_id == user.id else 'borrower'

    def get_available_actions(self, order):
        return services.available_actions(order, self.context['request'].user)


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