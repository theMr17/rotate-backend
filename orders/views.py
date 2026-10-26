from django.db.models import Exists, OuterRef, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import BookingRefUnavailable, InvalidTransition, Offer, Order
from .serializers import CounterOfferSerializer, OrderSerializer, RentalRequestSerializer

class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):   
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Order.objects.filter(Q(borrower=user) | Q(lender=user))
            .select_related('item', 'borrower', 'lender', 'cancelled_by')
            .prefetch_related('offers')
        )
        if self.action != 'list':
            return queryset
        return self._filter(queryset, user, self.request.query_params)

    def _filter(self, queryset, user, params):
        role = params.get('role')
        if role == 'borrower':
            queryset = queryset.filter(borrower=user)
        elif role == 'lender':
            queryset = queryset.filter(lender=user)

        # ?status=accepted or ?status=accepted,active
        if params.get('status'):
            statuses = [value.strip() for value in params['status'].split(',') if value.strip()]
            unknown = sorted(set(statuses) - set(Order.Status.values))
            if unknown:
                raise ValidationError({
                    'status': f"Unknown status: {', '.join(unknown)}. "
                              f"Choose from: {', '.join(Order.Status.values)}."
                })
            queryset = queryset.filter(status__in=statuses)

        # ?needs_action=true: a pending offer from the other party is waiting on me.
        needs_action = params.get('needs_action', '').lower()
        if needs_action in ('true', '1'):
            waiting_on_me = Offer.objects.filter(
                order=OuterRef('pk'), status=Offer.Status.PENDING,
            ).exclude(proposed_by=user)
            queryset = queryset.filter(Exists(waiting_on_me), status=Order.Status.REQUESTED)
        elif needs_action not in ('', 'false', '0'):
            raise ValidationError({'needs_action': 'Use true or false.'})
        return queryset

    def create(self, request):
        serializer = RentalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = self._run(
            services.request_rental, borrower=request.user, **serializer.validated_data
        )
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def counter(self, request, pk=None):
        serializer = CounterOfferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._run(
            services.counter_offer, self.get_object(), request.user,
            **serializer.validated_data,
        )
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        self._run(services.accept_offer, self.get_object(), request.user)
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        self._run(services.reject_offer, self.get_object(), request.user)
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self._transition(services.cancel_order)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._transition(services.start_order)

    @action(detail=True, methods=['post'], url_path='return')
    def mark_returned(self, request, pk=None):
        return self._transition(services.return_order)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self._transition(services.complete_order)

    @action(detail=True, methods=['post'])
    def dispute(self, request, pk=None):
        return self._transition(services.dispute_order)

    def _transition(self, func):
        self._run(func, self.get_object(), self.request.user)
        return Response(self.get_serializer(self.get_object()).data)

    def _run(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except services.OrderPermissionError as error:
            raise PermissionDenied(str(error))
        except (services.OrderError, InvalidTransition, BookingRefUnavailable) as error:
            raise ValidationError({'detail': str(error)})