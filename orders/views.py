from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import InvalidTransition, Order
from .serializers import CounterOfferSerializer, OrderSerializer, RentalRequestSerializer

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Order.objects.filter(Q(borrower=user) | Q(lender=user))
            .select_related('item', 'borrower', 'lender')
            .prefetch_related('offers__proposed_by')
        )
        role = self.request.query_params.get('role')
        if role == 'borrower':
            queryset = queryset.filter(borrower=user)
        elif role == 'lender':
            queryset = queryset.filter(lender=user)
        return queryset

    def create(self, request):
        serializer = RentalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = self._run(
            services.request_rental, borrower=request.user, **serializer.validated_data
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def counter(self, request, pk=None):
        serializer = CounterOfferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._run(
            services.counter_offer, self.get_object(), request.user,
            **serializer.validated_data,
        )
        return Response(OrderSerializer(self.get_object()).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        self._run(services.accept_offer, self.get_object(), request.user)
        return Response(OrderSerializer(self.get_object()).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        self._run(services.reject_offer, self.get_object(), request.user)
        return Response(OrderSerializer(self.get_object()).data)

    def _run(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (services.OrderError, InvalidTransition) as error:
            raise ValidationError({'detail': str(error)})