from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from . import services
from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer

User = get_user_model()


class ReviewCreateView(APIView):
    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            review = services.create_review(
                data['order'], request.user, data['rating'], data['comment']
            )
        except services.ReviewError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class OrderReviewStatusView(APIView):
    def get(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        user = request.user
        if user.pk not in (order.borrower_id, order.lender_id):
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        reviews = {r.reviewer_id: r for r in order.reviews.select_related('reviewer')}
        other_id = order.lender_id if user.pk == order.borrower_id else order.borrower_id
        mine, theirs = reviews.get(user.pk), reviews.get(other_id)
        blocker = services.review_blocker(order, user)
        return Response({
            'can_review': blocker is None,
            'reason': blocker,
            'my_review': ReviewSerializer(mine).data if mine else None,
            'their_review': ReviewSerializer(theirs).data if theirs else None,
        })


class ReviewPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class UserReviewListView(ListAPIView):
    serializer_class = ReviewSerializer
    pagination_class = ReviewPagination

    def get_queryset(self):
        user = get_object_or_404(User, pk=self.kwargs['user_id'], is_active=True)
        queryset = Review.objects.filter(reviewee=user).select_related('reviewer')
        role = self.request.query_params.get('role')
        if role in Review.Role.values:
            queryset = queryset.filter(reviewee_role=role)
        return queryset
