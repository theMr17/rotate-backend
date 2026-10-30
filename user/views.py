from django.contrib.auth import authenticate
from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from geo.fields import LatLngField
from uploads import ImageUploadField

from .models import User
from .photos import delete_profile_photo, upload_profile_photo


class RegisterSerializer(serializers.ModelSerializer):
	password = serializers.CharField(write_only=True, min_length=8)
	home_location = LatLngField(required=False, allow_null=True)

	class Meta:
		model = User
		fields = ('name', 'email', 'password', 'phone', 'location', 'home_location', 'home_address_label', 'role')
		extra_kwargs = {'role': {'read_only': True}}

	def create(self, validated_data):
		return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
	email = serializers.EmailField()
	password = serializers.CharField(write_only=True)

	def validate(self, attrs):
		user = authenticate(email=attrs['email'], password=attrs['password'])
		if not user:
			raise serializers.ValidationError('Invalid email or password.')
		if not user.is_active:
			raise serializers.ValidationError('This account is inactive.')
		attrs['user'] = user
		return attrs


class ProfileSerializer(serializers.ModelSerializer):
	home_location = LatLngField(required=False, allow_null=True)

	class Meta:
		model = User
		fields = (
			'id', 'name', 'email', 'phone', 'location', 'home_location', 'home_address_label',
			'profile_photo_url', 'role', 'is_verified', 'created_at', 'updated_at',
		)
		read_only_fields = (
			'id', 'email', 'profile_photo_url', 'role', 'is_verified', 'created_at', 'updated_at',
		)


class ProfilePhotoSerializer(serializers.Serializer):
	photo = ImageUploadField()


def token_response(user):
	refresh = RefreshToken.for_user(user)
	return {'access': str(refresh.access_token), 'refresh': str(refresh)}


class RegisterView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		serializer = RegisterSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			user = serializer.save()
		except IntegrityError:
			return Response({'detail': 'A user with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)
		return Response(token_response(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		serializer = LoginSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		return Response(token_response(serializer.validated_data['user']))


class ProfileView(APIView):
	def get(self, request):
		return Response(ProfileSerializer(request.user).data)

	def patch(self, request):
		serializer = ProfileSerializer(request.user, data=request.data, partial=True)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return Response(serializer.data)


class ProfilePhotoView(APIView):
	parser_classes = [MultiPartParser, FormParser]

	def post(self, request):
		serializer = ProfilePhotoSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		user = request.user
		# Raises ImageStorageNotConfigured (503) / ImageUploadFailed (502).
		url, public_id = upload_profile_photo(user, serializer.validated_data['photo'])

		old_public_id = user.profile_photo_public_id
		user.profile_photo_url = url
		user.profile_photo_public_id = public_id
		user.save(update_fields=['profile_photo_url', 'profile_photo_public_id', 'updated_at'])
		if old_public_id and old_public_id != public_id:
			delete_profile_photo(old_public_id)

		return Response(ProfileSerializer(user).data)

	def delete(self, request):
		user = request.user
		public_id = user.profile_photo_public_id
		user.profile_photo_url = ''
		user.profile_photo_public_id = ''
		user.save(update_fields=['profile_photo_url', 'profile_photo_public_id', 'updated_at'])
		delete_profile_photo(public_id)
		return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		refresh_token = request.data.get('refresh')
		if not refresh_token:
			return Response({'refresh': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

		try:
			RefreshToken(refresh_token).blacklist()
		except TokenError:
			return Response({'refresh': ['Invalid or expired refresh token.']}, status=status.HTTP_400_BAD_REQUEST)

		return Response(status=status.HTTP_204_NO_CONTENT)
