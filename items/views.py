from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Item
from .permissions import IsOwnerOrReadOnly
from .serializers import ItemSerializer
from .models import Item


class ItemViewSet(viewsets.ModelViewSet):

    serializer_class = ItemSerializer

    permission_classes = [
        IsAuthenticated,
        IsOwnerOrReadOnly
    ]

    def get_queryset(self):
        return Item.objects.all()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)