import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from user.factories import UserFactory


@pytest.fixture
def api_client():
    """An unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def user(db):
    """A saved user whose password is user.factories.DEFAULT_PASSWORD."""
    return UserFactory()


@pytest.fixture
def auth_client(user):
    """A client sending a real JWT access token for ``user``.

    Separate from ``api_client`` so a test can use both side by side.
    """
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    client.user = user
    return client
