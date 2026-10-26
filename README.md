# Rotate Backend

Backend service for the Rotate rental platform, built using Django, Django REST Framework, and PostgreSQL.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/theMr17/rotate-backend.git
cd rotate-backend
```

### 2. Create a virtual environment

Do not commit or push the virtual environment (`venv`) to the repository. Each developer should create their own environment locally.

```bash
python -m venv venv
```

Activate it:

```bash
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

For development (adds pytest, pytest-django, pytest-cov and factory_boy), install the dev requirements instead; they include `requirements.txt`:

```bash
pip install -r requirements-dev.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root and configure the environment variables required by `config/settings.py`, including database credentials and the Django secret key.

Do not commit `.env` or expose secret keys and credentials.

### 5. Start PostgreSQL

If using the project's Docker Compose configuration:

```bash
docker compose up -d
```

Ensure the database configuration in `.env` matches the PostgreSQL service configuration.

### 6. Apply migrations

```bash
python manage.py migrate
```

### 7. Start the development server

```bash
python manage.py runserver
```

The backend will be available at:

```text
http://127.0.0.1:8000/
```

## Running Tests

Tests run with [pytest](https://docs.pytest.org/) and [pytest-django](https://pytest-django.readthedocs.io/) against the Docker Postgres. Make sure the database is up (`docker compose up -d`) and your `.env` points at it; the database user needs permission to create the throwaway `test_<POSTGRES_DB>` database.

```bash
pip install -r requirements-dev.txt
pytest
```

Every run prints a coverage summary to the terminal and writes an HTML report to `htmlcov/index.html`. Configuration lives in `pyproject.toml`.

CI (`.github/workflows/tests.yml`) runs the same suite against Postgres on every pull request and fails if coverage of `items/` or `orders/` drops below 80%. To run the same check locally after `pytest`:

```bash
coverage report --include='items/*' --fail-under=80
coverage report --include='orders/*' --fail-under=80
```

Useful variations:

```bash
pytest user/                      # one app
pytest orders/tests.py -k cancel  # tests matching a name
pytest --reuse-db                 # keep the test DB between runs (faster; drop the flag after adding migrations)
pytest --no-cov                   # skip coverage, e.g. when debugging with --pdb
```

### Writing tests

- Put tests in `<app>/tests.py` or `<app>/test_*.py`. Plain `def test_...()` functions and Django `TestCase`/`APITestCase` classes both work.
- Functions that touch the database need `@pytest.mark.django_db` (or `pytestmark = pytest.mark.django_db` at module level).
- Use `reverse('<url-name>')` instead of hard-coding paths.
- Shared fixtures in `conftest.py`:
  - `api_client`: unauthenticated DRF `APIClient`
  - `user`: a saved user whose password is `user.factories.DEFAULT_PASSWORD`
  - `auth_client`: an `APIClient` sending a real JWT for `user` (also available as `auth_client.user`)
- Factories (factory_boy) build valid model instances with sensible defaults:
  - `user.factories.UserFactory`
  - `items.factories.ItemFactory`: creates an owner too
  - `orders.factories.OrderFactory`: lender is the item's owner, and a `requested` order gets a pending offer (`offer=False` to skip it)
  - `orders.factories.OfferFactory`

```python
import pytest
from django.urls import reverse

from orders.factories import OrderFactory
from orders.models import Order

@pytest.mark.django_db
def test_lender_can_start_accepted_order(api_client):
    order = OrderFactory(status=Order.Status.ACCEPTED)
    api_client.force_authenticate(order.lender)
    response = api_client.post(reverse('order-start', args=[order.pk]))
    assert response.status_code == 200
```

## API Documentation

**Base URL**

```text
http://127.0.0.1:8000/api/v1/
```

Unless otherwise specified, send JSON request bodies with:

```http
Content-Type: application/json
```

### Authentication

The API uses JWT (JSON Web Token) authentication.

For protected endpoints, include the access token in the request:

```http
Authorization: Bearer <access_token>
```

First register or log in to obtain an access token and a refresh token. Use the access token for authenticated API requests.

### 1. User Endpoints

| Method | Endpoint | Description | Authentication |
|---|---|---|---|
| POST | `/user/register` | Register a new user | Not required |
| POST | `/user/login` | Log in and obtain JWT tokens | Not required |
| POST | `/user/logout` | Log out | Depends on view implementation |
| GET | `/user/profile` | Retrieve the current user's profile | Required |
| POST | `/user/token/refresh` | Obtain a new access token | Refresh token required |

#### Register a user

**POST** `/user/register`

Example request:

```json
{
  "name": "Ankit Test",
  "email": "ankit.test@example.com",
  "password": "TestPass123!",
  "phone": "9876543210",
  "location": "Kolkata, India"
}
```

The `name`, `email`, and `password` fields are expected for registration. `phone` and `location` can be omitted if optional in the registration serializer.

#### Login

**POST** `/user/login`

```json
{
  "email": "ankit.test@example.com",
  "password": "TestPass123!"
}
```

A successful login returns JWT tokens:

```json
{
  "access": "<access_token>",
  "refresh": "<refresh_token>"
}
```

Use the `access` token as a Bearer token for protected endpoints.

#### Refresh an access token

**POST** `/user/token/refresh`

```json
{
  "refresh": "<refresh_token>"
}
```

### 2. Item Endpoints

Items represent objects that users can list for rent.

| Method | Endpoint | Description | Authentication |
|---|---|---|---|
| GET | `/items/` | List available items | Not required |
| POST | `/items/` | Create a rental listing | Required |
| GET | `/items/<id>/` | Retrieve an item | Not required |
| PATCH | `/items/<id>/` | Update an item | Owner only |
| DELETE | `/items/<id>/` | Delete an item | Owner only |

#### Create an item

**POST** `/items/`

Requires a valid access token.

```json
{
  "title": "Canon EOS 1500D DSLR Camera",
  "description": "DSLR camera with an 18-55mm lens, suitable for photography.",
  "category": "Electronics",
  "hourly_rate": "100.00",
  "deposit_amount": "2000.00",
  "condition": "GOOD",
  "status": "AVAILABLE"
}
```

The `owner` is assigned from the authenticated user and should not be supplied in the request body.

The `condition` and `status` values must match the choices defined by the Item model.

#### List available items

**GET** `/items/`

Returns available listings.

Optional query parameters supported by the current implementation:

- `category` — filter by category.
- `search` — search item titles and descriptions.
- `mine=true` — retrieve the authenticated user's own listings.

Example:

```text
GET /api/v1/items/?category=Electronics&search=camera
```

The `mine=true` query requires authentication.

#### Retrieve an item

**GET** `/items/<id>/`

Replace `<id>` with the item's database ID.

Example:

```text
GET /api/v1/items/1/
```

#### Update an item

**PATCH** `/items/<id>/`

Requires authentication as the item's owner.

Example:

```json
{
  "hourly_rate": "120.00",
  "description": "Updated camera rental description."
}
```

Only the fields being updated need to be included.

#### Delete an item

**DELETE** `/items/<id>/`

Requires authentication as the item's owner.

### 3. Order Endpoints

Orders represent rental requests and their lifecycle.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/orders/` | List orders accessible to the user |
| POST | `/orders/` | Create a rental request |
| GET | `/orders/<id>/` | Retrieve an order |
| POST | `/orders/<id>/counter/` | Submit a counter-offer |
| POST | `/orders/<id>/accept/` | Accept an order or offer |
| POST | `/orders/<id>/reject/` | Reject an order or offer |

All order operations should be performed with a valid access token unless the relevant view explicitly allows public access.

The order workflow supports states such as:

`requested -> accepted -> active -> returned -> completed`

Orders may also enter a disputed state.

#### Place an order

**POST** `/orders/`

Example request body — verify the required fields against the current order serializer:

```json
{
  "item": 1,
  "start_time": "2026-10-20T10:00:00+05:30",
  "end_time": "2026-10-20T12:00:00+05:30",
  "hourly_rate": "50.00",
  "message": "I would like to rent this item."
}
```

- Replace `item` with an existing item's ID.
- The requested start time must be before the end time.
- Use an account different from the item's owner when placing a rental request.
- Do not send fields that the serializer calculates or assigns automatically.

The exact request fields and order state transitions are determined by the current order serializer and service implementation.

### 4. Health Check

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health/` | Check whether the backend health endpoint responds |

Example:

```text
GET http://127.0.0.1:8000/health/
```

### API Usage Notes

- Use `POST` to create resources, `GET` to retrieve them, `PATCH` to partially update them, and `DELETE` to delete them.
- Send a valid access token in the `Authorization` header for protected requests.
- Use existing database IDs when referencing users, items, or orders.
- A `401 Unauthorized` response usually indicates missing, invalid, or expired authentication.
- A `403 Forbidden` response generally indicates insufficient permissions.
- A `404 Not Found` response indicates that the requested resource or endpoint could not be found.
- A `400 Bad Request` response generally indicates invalid input or failed validation.

## Project Structure

```text
rotate-backend/
├── config/          # Django project configuration
├── health/          # Health check application
├── user/            # User model and authentication APIs
├── items/           # Item model and listing APIs
├── orders/          # Orders and offers APIs
├── conftest.py      # Shared pytest fixtures
├── manage.py        # Django management utility
├── pyproject.toml   # pytest and coverage configuration
├── requirements.txt # Python dependencies
├── requirements-dev.txt # Test/dev dependencies
└── .gitignore       # Git ignored files
```

## Development Workflow

Create a separate feature branch before working on a feature:

```bash
git checkout main
git pull origin main
git checkout -b feature/<feature-name>
```

Commit your changes and create a pull request into `main` when the feature is ready.

Before submitting a PR, verify that migrations are included, secrets are excluded, and `pytest` passes.

## Tech Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- SimpleJWT
- Docker Compose
- REST API
