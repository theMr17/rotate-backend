# Rotate Backend

Backend service for the Rotate rental platform, built using Django and Django REST Framework.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/theMr17/rotate-backend.git
cd rotate-backend
```

### 2. Create a virtual environment

Do not commit or push the virtual environment (`venv`) to the repository. Each developer should create their own virtual environment locally.

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

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Start the development server

```bash
python manage.py runserver
```

The backend will be available at:

```text
http://127.0.0.1:8000/
```

## Project Structure

```text
rotate-backend/
├── config/          # Django project configuration
├── health/          # Health check application
├── manage.py        # Django management utility
├── requirements.txt # Python dependencies
└── .gitignore       # Git ignored files
```

## Development

Create a separate feature branch before working on a feature:

```bash
git checkout main
git pull origin main
git checkout -b feature/<feature-name>
```

Commit your changes and create a pull request into `main` when the feature is ready.

## Tech Stack

* Python
* Django
* Django REST Framework
* PostgreSQL
* REST API
