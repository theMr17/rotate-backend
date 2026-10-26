from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RentalNeed
from .serializers import RentalNeedSerializer


class RentalNeedListCreateView(APIView):

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):

        needs = RentalNeed.objects.select_related("requester").all()

        # ?mine=true returns the current user's own requests.
        mine = request.query_params.get("mine", "").lower()

        if mine == "true":
            if not request.user.is_authenticated:
                raise NotAuthenticated(
                    "Login is required to view your requests."
                )

            needs = needs.filter(requester=request.user)

        else:
            # Public discovery feed:
            # Show only open requests from other users.
            needs = needs.filter(status=RentalNeed.Status.OPEN)

            if request.user.is_authenticated:
                needs = needs.exclude(requester=request.user)

        # Search title, description and category.
        search = request.query_params.get("search")

        if search:
            needs = needs.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
            )

        # Category filter.
        category = request.query_params.get("category")

        if category:
            needs = needs.filter(category__iexact=category)

        # Location filter.
        location = request.query_params.get("location")

        if location:
            needs = needs.filter(location__icontains=location)

        serializer = RentalNeedSerializer(needs, many=True)

        return Response(serializer.data)

    def post(self, request):

        serializer = RentalNeedSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        # Always assign the logged-in user as requester.
        need = serializer.save(requester=request.user)

        return Response(
            RentalNeedSerializer(need).data,
            status=status.HTTP_201_CREATED,
        )


class RentalNeedDetailView(APIView):

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        return get_object_or_404(
            RentalNeed.objects.select_related("requester"),
            pk=pk,
        )

    def get(self, request, pk):

        need = self.get_object(pk)

        serializer = RentalNeedSerializer(need)

        return Response(serializer.data)

    def patch(self, request, pk):

        need = self.get_object(pk)

        # Only the person who created the request can edit it.
        if need.requester_id != request.user.id:
            raise PermissionDenied(
                "You cannot edit someone else's rental request."
            )

        # Only open requests can be edited.
        if need.status != RentalNeed.Status.OPEN:
            raise ValidationError(
                {"detail": "Only open requests can be edited."}
            )

        serializer = RentalNeedSerializer(
            need,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(serializer.data)


class RentalNeedCancelView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        # Lock the record while cancelling it.
        need = get_object_or_404(
            RentalNeed.objects.select_for_update(),
            pk=pk,
        )

        if need.requester_id != request.user.id:
            raise PermissionDenied(
                "You cannot cancel someone else's rental request."
            )

        if need.status != RentalNeed.Status.OPEN:
            raise ValidationError(
                {"detail": "Only open requests can be cancelled."}
            )

        need.status = RentalNeed.Status.CANCELLED

        need.save(update_fields=["status", "updated_at"])

        return Response(
            RentalNeedSerializer(need).data,
            status=status.HTTP_200_OK,
        )