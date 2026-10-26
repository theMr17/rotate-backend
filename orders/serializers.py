from rest_framework import serializers
from decimal import Decimal
from items.models import Item
from . import services
from .models import Offer, Order

# Statuses from which the two parties have a confirmed deal and may see each
# other's contact details. Cancelled is excluded: it may never have been accepted.
CONTACT_VISIBLE_STATUSES = {
    Order.Status.ACCEPTED, Order.Status.ACTIVE, Order.Status.RETURNED,
    Order.Status.DISPUTED, Order.Status.COMPLETED,
}


class OfferSerializer(serializers.ModelSerializer):
    proposed_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Offer
        fields = ['id', 'proposed_by', 'hourly_rate', 'message', 'status', 'created_at']


def participant_data(user, include_contact):
    return {
        'id': user.id,
        'name': user.name,
        # TODO: Update these placeholders when profile photos and reliability scores exist on User.
        'avatar': None,
        'reliability_score': None,
        'contact': {
            'email': user.email,
            'phone': user.phone,
            'location': user.location,
        } if include_contact else None,
    }


class OrderSerializer(serializers.ModelSerializer):
    """Order as seen by one of its participants (needs `request` in context)."""

    item = serializers.SerializerMethodField()
    borrower = serializers.SerializerMethodField()
    lender = serializers.SerializerMethodField()
    cancelled_by = serializers.PrimaryKeyRelatedField(read_only=True)
    offers = OfferSerializer(many=True, read_only=True)
    my_role = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'booking_ref', 'item', 'borrower', 'lender', 'my_role', 'allowed_actions',
            'start_time', 'end_time',
            'status', 'agreed_hourly_rate', 'rental_fee', 'platform_fee', 'deposit_amount',
            'total_due', 'offers',
            'started_at', 'returned_at', 'completed_at', 'cancelled_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def _user(self):
        return self.context['request'].user

    def _contact_visible(self, order):
        return order.status in CONTACT_VISIBLE_STATUSES

    def get_item(self, order):
        return {
            'id': order.item_id,
            'title': order.item.title,
            'cover_photo': None,  # placeholder until items have photos
            'owner': order.item.owner_id,
        }

    def get_borrower(self, order):
        return participant_data(order.borrower, self._contact_visible(order))

    def get_lender(self, order):
        return participant_data(order.lender, self._contact_visible(order))

    def get_my_role(self, order):
        return services.role_of(order, self._user())

    def get_allowed_actions(self, order):
        return services.allowed_actions(order, self._user())


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
