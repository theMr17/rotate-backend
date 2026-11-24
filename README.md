# Rotate Backend

Backend service for the Rotate rental platform, built using Django, Django REST Framework, and PostgreSQL.



# AI Assistance Declaration

### i. Rental Needs
•⁠  ⁠*Frontend:* AI assistance was used in ⁠ app/rental-needs/ ⁠, to implement the rental-request feature. For example ⁠ app/rental-needs/[id]/page.tsx ⁠ file. This feature was developed towards the later stages and involved complex integration with the existing Orders and Offers workflow.

•⁠  ⁠*Backend:* AI assistance was used in ⁠ rental_needs/signals.py ⁠, especially for integrating Rental Needs with the order lifecycle.

### ii. Rating and Review System
AI assistance helped in developing this feature. This included developing the underlying functionality, connecting the APIs, and integrating the feature into the existing application workflow. ex -

•⁠  ⁠*Frontend:*  TrustBadges.tsx

•⁠  ⁠*Backend:*   trust/

## Objective

Rotate is a peer-to-peer rental platform that lets people rent everyday items from others nearby instead of buying things they need only briefly. It aims to:

- Let owners list items with an hourly rate, security deposit and condition.
- Let borrowers request a time slot and agree on a price through offers and counter-offers.
- Manage the full rental lifecycle (request, accept, handover, return, complete), with photo evidence and admin-resolved disputes.
- Let users post a "rental need" that item owners can respond to.
- Build trust between users through ratings and reviews.

The project has two parts: a Next.js frontend ([rotate-frontend](https://github.com/theMr17/rotate-frontend)) and a Django REST backend ([rotate-backend](https://github.com/theMr17/rotate-backend)).

## Getting Started

### Prerequisites

- **Python 3.12 or newer** (required by Django 6.1)
- **Docker** with Docker Compose, to run PostgreSQL + PostGIS
- **GDAL and GEOS** system libraries, needed by GeoDjango for the user's home location:

```bash
# macOS (Homebrew)
brew install gdal geos

# Ubuntu / Debian
sudo apt install gdal-bin libgdal-dev libgeos-dev
```

On Windows, install GDAL through [OSGeo4W](https://trac.osgeo.org/osgeo4w/). If Django reports that it could not find GDAL or GEOS, set `GDAL_LIBRARY_PATH` and `GEOS_LIBRARY_PATH` in `config/settings.py` to the library files. On Apple Silicon with Homebrew these are `/opt/homebrew/opt/gdal/lib/libgdal.dylib` and `/opt/homebrew/opt/geos/lib/libgeos_c.dylib`.

- A free [Cloudinary](https://cloudinary.com) account *(optional)*. It's only needed for photo uploads; everything else works without it.

### 1. Clone the repository

```bash
git clone https://github.com/theMr17/rotate-backend.git
cd rotate-backend
```

### 2. Create a virtual environment

Do not commit or push the virtual environment (`venv`) to the repository. Each developer should create their own environment locally.

```bash
python -m venv venv      # use python3 if `python` points to Python 2 or is missing
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

### 4. Configure environment variables

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Then edit the values:

| Variable | What to set |
|---|---|
| `DJANGO_SECRET_KEY` | Any long random string |
| `DJANGO_DEBUG` | `true` for local development |
| `DJANGO_ALLOWED_HOSTS` | Keep `localhost,127.0.0.1` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Any values. Docker Compose creates the database with them. |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Keep `localhost` and `5433` (the port Docker Compose exposes) |
| `POSTGRES_SSLMODE` | Keep `prefer` for local Docker. The default is `require`, which fails locally. |
| `CORS_ALLOWED_ORIGINS` | The frontend address, `http://localhost:3000` |
| `CLOUDINARY_*` | Your Cloudinary credentials. Leave as-is to skip photo uploads (they return a 503 error). |

To generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Do not commit `.env` or expose secret keys and credentials.

### 5. Start PostgreSQL

If using the project's Docker Compose configuration:

```bash
docker compose up -d
```

Ensure the database configuration in `.env` matches the PostgreSQL service configuration. Docker Compose reads the `POSTGRES_*` values from `.env`, so create `.env` (step 4) before running this.

On Apple Silicon Macs, if the image fails to pull ("no matching manifest"), add `platform: linux/amd64` under the `db` service in `docker-compose.yml`.

To stop the database later, run `docker compose stop`. Your data is kept in a Docker volume.

### 6. Apply migrations

```bash
python manage.py migrate
```

Optionally, create an admin account. You need it for the Django admin panel at `/admin/` and to resolve disputed orders:

```bash
python manage.py createsuperuser
```

### 7. Start the development server

```bash
python manage.py runserver
```

The backend will be available at:

```text
http://127.0.0.1:8000/
```

Check it is working by opening `http://127.0.0.1:8000/health/`, which should return `{"status": "ok"}`.

To use the app in a browser, set up the frontend next: [rotate-frontend](https://github.com/theMr17/rotate-frontend).

## Code Organization

The project is a Django **project** (`config/`) made of several **apps**, one per feature. A request flows: `config/urls.py` → the app's `urls.py` → `views.py` → `serializers.py` (validation) → `services.py` (business rules) → `models.py` (database).

```text
rotate-backend/
├── config/          project settings and the main URL router
├── user/            accounts, JWT login, profiles
├── items/           item listings
├── orders/          rental orders, offers, lifecycle, condition photos
├── rental_needs/    "I need X" requests that owners respond to
├── trust/           reviews and reliability
├── health/          health-check endpoint
├── uploads/         shared Cloudinary image-upload helpers
├── geo/             shared lat/lng serializer field
├── manage.py
├── requirements.txt
└── docker-compose.yml
```

### Files found in every app

| File | Role |
|---|---|
| `models.py` | Database tables, written as Python classes |
| `migrations/` | Auto-generated history of table changes (`makemigrations` / `migrate`) |
| `serializers.py` | Converts models ↔ JSON and validates incoming data |
| `views.py` | Handles requests and returns responses |
| `urls.py` | Maps the app's URLs to its views |
| `services.py` | Business rules, kept out of the views |
| `admin.py` | How the models appear in the `/admin/` panel |
| `apps.py` | The app's configuration class |
| `tests.py` | Automated tests |
| `__init__.py` | Marks the folder as a Python package |

### Root and `config/`

| File | Role |
|---|---|
| `manage.py` | Command-line entry point (`runserver`, `migrate`, …) |
| `requirements.txt` | Python dependencies with pinned versions |
| `docker-compose.yml` | Runs PostgreSQL + PostGIS on port 5433 |
| `.env.example` | Template for the environment variables |
| `config/settings.py` | All settings: installed apps, database, JWT and DRF defaults, CORS, Cloudinary |
| `config/urls.py` | Main router; sends `/api/v1/...` to each app's `urls.py` |
| `config/wsgi.py`, `config/asgi.py` | Entry points for production servers |

### `user/`: accounts and profiles

| File | Role |
|---|---|
| `models.py` | Custom `User` (login by email), with home location (PostGIS point) and profile photo |
| `views.py` | Register, login, logout (token blacklist), own profile, public profile, profile photo; also holds this app's serializers |
| `photos.py` | Uploads and deletes profile photos on Cloudinary |
| `urls.py` | `/user/register`, `/login`, `/logout`, `/profile`, `/profile/photo`, `/token/refresh` |

### `items/`: listings

| File | Role |
|---|---|
| `models.py` | `Item`: owner, title, category, hourly rate, deposit, condition, status |
| `serializers.py` | `ItemSerializer`, with minimum-price validation |
| `permissions.py` | `IsOwnerOrReadOnly`: anyone can view, only the owner can edit or delete |
| `views.py` | List and search, create, view, update, delete (409 if the item has orders) |
| `urls.py` | `/items/`, `/items/<id>/` |

### `orders/`: the rental lifecycle

| File | Role |
|---|---|
| `models.py` | `Order` (state machine with `ALLOWED_TRANSITIONS`), `Offer` (price negotiation), `ConditionPhoto` (pre/post photos) |
| `services.py` | All order rules: request, counter, accept (with row locks), reject, cancel, start, return, complete, dispute, resolve, `available_actions` |
| `serializers.py` | Order JSON (including `my_role` and `available_actions`) and input validation for each action |
| `views.py` | `OrderViewSet`: list, detail, create, plus actions `/counter/`, `/accept/`, `/reject/`, `/cancel/`, `/start/`, `/return/`, `/complete/`, `/dispute/`, `/photos/`, `/resolve/` |
| `photos.py` | Uploads condition photos to Cloudinary |
| `urls.py` | Router that generates the `/orders/` URLs |

### `rental_needs/`: reverse marketplace

| File | Role |
|---|---|
| `models.py` | `RentalNeed` (what someone needs, open/fulfilled/cancelled) and `RentalNeedResponse` (links a provider's offer to an order) |
| `services.py` | `respond_to_need` (creates an order and offer) and `cancel_rental_need` |
| `signals.py` | When an offer is accepted, marks the need fulfilled and rejects competing responses |
| `apps.py` | Loads `signals.py` at startup |
| `serializers.py` | Need, response and detail serializers, with date validation |
| `views.py` | List and create, detail and edit, cancel, respond |
| `urls.py` | `/rental-needs/`, `/<id>/`, `/<id>/cancel/`, `/<id>/respond/` |

### `trust/`: reviews and reliability

| File | Role |
|---|---|
| `models.py` | `Review` (1–5 stars, one per person per order) and `ReliabilityStats` |
| `services.py` | Review rules, rating averages, `trust_summary` shown on profiles |
| `serializers.py` | Review input and output |
| `views.py` | Create a review, review status for an order, a user's reviews (paginated) |
| `urls.py` | `/reviews`, `/reviews/order/<id>`, `/users/<id>/reviews` |

### Shared helpers and health

| File | Role |
|---|---|
| `uploads/storage.py` | `upload_image` / `delete_image` wrappers around Cloudinary |
| `uploads/fields.py` | `ImageUploadField`: JPEG/PNG/WebP only, up to 5 MB |
| `uploads/exceptions.py` | Clear API errors: 503 when Cloudinary isn't configured, 502 when an upload fails |
| `geo/fields.py` | `LatLngField`: converts `{"lat", "lng"}` JSON ↔ a PostGIS point |
| `health/views.py` | `GET /health/`, returns `{"status": "ok"}` |
| `health/tests.py` | Tests for the health endpoint |

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

See [Code Organization](#code-organization) above for the folder layout and the role of each file.

## Development Workflow

Create a separate feature branch before working on a feature:

```bash
git checkout main
git pull origin main
git checkout -b feature/<feature-name>
```

Commit your changes and create a pull request into `main` when the feature is ready.

Before submitting a PR, verify that migrations are included, secrets are excluded, and the relevant API endpoints have been tested.

## Tech Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- SimpleJWT
- Docker Compose
- REST API
