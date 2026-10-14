from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('orders', OrderViewSet, basename='order')

urlpatterns = router.urls