# 🛒 E-commerce Store REST API

[![CI Pipeline](https://github.com/TrMaksym/E-commerce-Store-API/actions/workflows/ci.yml/badge.svg)](https://github.com/TrMaksym/E-commerce-Store-API/actions)
[![Coverage](https://img.shields.io/badge/Coverage-96%25-brightgreen.svg)](https://github.com/TrMaksym/E-commerce-Store-API)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-darkgreen.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.16-red.svg)](https://www.django-rest-framework.org/)

A production-ready RESTful API for an e-commerce platform built with Django REST Framework, featuring atomic checkout operations, Stripe payment processing, asynchronous Celery workers, Redis caching, and automated CI quality checks.

---

## ⚡ Key Features

* **Product Catalog:** Hierarchical category trees, brand filtering, product variants (SKU, price, stock tracking), and image galleries.
* **Filtering & Search:** Dynamic querying via `django-filter` across price ranges, categories, brands, and real-time inventory status.
* **Cart Management:** Persistent shopping carts for authenticated users with automatic subtotal calculation and inventory checks.
* **Checkout & Orders:**
  * Atomic database transactions (`transaction.atomic`) to ensure consistent inventory deduction.
  * Promo code engine supporting usage limits, percentage discounts, and expiration boundaries.
* **Payment Integration:** Stripe Checkout session management, secure webhook validation (`checkout.session.completed`), and idempotent payment records.
* **Background Tasks (Celery & Redis):**
  * Asynchronous transactional emails triggered via `on_commit` hooks.
  * Celery Beat cron tasks to cancel stale unpaid orders and replenish reserved stock.
* **Performance & Caching:** Redis response caching with targeted invalidation signals triggered on product and catalog mutations.
* **Security & Permissions:** Stateless JWT authentication (`SimpleJWT`) and granular role-based access control (Admin, Customer, Resource Owner).
* **OpenAPI Documentation:** Interactive documentation via Swagger UI and ReDoc powered by `drf-spectacular`.

---

## 🛠 Tech Stack

* **Core:** Python, Django, Django REST Framework
* **Database:** PostgreSQL (Production / Docker), SQLite (Local / Test suite)
* **Tasks & Caching:** Celery, Redis, Celery Beat
* **Payments:** Stripe API
* **Testing:** `pytest`, `pytest-django`, `pytest-cov` (92 unit/integration tests, 96% coverage)
* **DevOps & CI:** Docker, Docker Compose, GitHub Actions

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/api/auth/token/` | Obtain JWT pair (access + refresh) | Public |
| `GET` | `/api/products/` | Filterable & searchable product catalog | Public |
| `GET` | `/api/products/{id}/` | Product details with variants & images | Public |
| `GET` | `/api/cart/` | Retrieve current user's cart | Authenticated |
| `POST` | `/api/cart/add/` | Add variant to cart with stock validation | Authenticated |
| `DELETE`| `/api/cart/items/{id}/`| Remove item from cart | Authenticated |
| `POST` | `/api/coupons/validate/`| Check coupon code validity & discount rate | Public |
| `POST` | `/api/orders/checkout/` | Atomic checkout (cart conversion or direct) | Authenticated |
| `POST` | `/api/orders/{id}/checkout/` | Initialize Stripe Checkout session | Authenticated |
| `POST` | `/api/webhooks/stripe/` | Process incoming Stripe events securely | Stripe Service |
| `GET/POST`| `/api/reviews/` | List or submit verified customer reviews | Auth / Buyer |

---

## 🚀 Getting Started

### Option 1: Run with Docker Compose (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/TrMaksym/E-commerce-Store-API.git
   cd E-commerce-Store-API
   ```

2. Create a `.env` file in the root directory:
   ```env
   DEBUG=True
   SECRET_KEY=your_secret_key_here
   POSTGRES_DB=ecommerce_db
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_HOST=db
   POSTGRES_PORT=5432
   REDIS_CACHE_URL=redis://redis:6379/1
   CELERY_BROKER_URL=redis://redis:6379/0
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_SUCCESS_URL=http://localhost:8000/api/payments/success/
   STRIPE_CANCEL_URL=http://localhost:8000/api/payments/cancel/
   ```

3. Build and launch services:
   ```bash
   docker compose up --build
   ```

4. Populate sample data (Optional):
   ```bash
   docker compose exec web python manage.py seed_data
   ```

The API will be available at `http://localhost:8000`.

---

### Option 2: Local Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   # Production dependencies:
   pip install -r requirements.txt

   # Development and test tools:
   pip install -r requirements-dev.txt
   ```

3. Run migrations and populate initial catalog:
   ```bash
   python manage.py migrate
   python manage.py seed_data
   ```

4. Start development server:
   ```bash
   python manage.py runserver
   ```

---

## 🧪 Testing & Quality Assurance

All third-party integrations (Stripe checkout & webhook signatures, Redis cache engines, and Celery workers) are isolated through mocks and transaction rollback fixtures.

Run the test suite with coverage report:
```bash
pytest
```

```text
---------- coverage: platform win32, python 3.13 -----------
Name                              Stmts   Miss  Cover
-----------------------------------------------------
store/models/*                      195      0   100%
store/permissions.py                 16      0   100%
store/serializers.py                198     10    95%
store/services/stripe_service.py     41      0   100%
store/signals.py                     11      0   100%
store/tasks.py                       28      0   100%
store/views.py                      199     18    91%
-----------------------------------------------------
TOTAL                              1747     66    96%
==================== 92 passed in 13.16s ====================
```

---

## 📖 API Documentation

Interactive OpenAPI schemas are available out of the box:
* **Swagger UI:** `http://localhost:8000/api/schema/swagger-ui/`
* **ReDoc:** `http://localhost:8000/api/schema/redoc/`
* **OpenAPI Raw Schema:** `http://localhost:8000/api/schema/`