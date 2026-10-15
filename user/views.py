from django.contrib.auth import authenticate
from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
	password = serializers.CharField(write_only=True, min_length=8)

	class Meta:
		model = User
		fields = ('name', 'email', 'password', 'phone', 'location', 'role')
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
	class Meta:
		model = User
		fields = ('id', 'name', 'email', 'phone', 'location', 'role', 'is_verified', 'created_at', 'updated_at')
		read_only_fields = fields


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
