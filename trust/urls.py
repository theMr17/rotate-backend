from django.urls import path

from .views import OrderReviewStatusView, ReviewCreateView, UserReviewListView

urlpatterns = [
    path('reviews', ReviewCreateView.as_view(), name='review-create'),
    path('reviews/order/<int:order_id>', OrderReviewStatusView.as_view(), name='order-review-status'),
    path('users/<int:user_id>/reviews', UserReviewListView.as_view(), name='user-reviews'),
]
