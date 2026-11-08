# Yourin — AI Virtual Interview Assistant

Yourin is an AI-powered virtual interview assistant developed as part of a course project. The application aims to support users in preparing for job interviews through CV management, job profile configuration, interview simulations, and AI-assisted feedback.

This repository contains a proof-of-concept (PoC) implementation consisting of a web-based frontend and a FastAPI backend.

Authentication is managed by **Supabase Auth**, while FastAPI provides the backend infrastructure for application-specific functionality. Some application workflows remain locally implemented using demo data.

---

## Table of Contents

- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Backend Setup](#backend-setup)
- [Frontend Setup](#frontend-setup)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Authentication Architecture](#authentication-architecture)
- [Development Tools](#development-tools)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend framework | FastAPI |
| Programming language | Python |
| Authentication | Supabase Auth |
| Database | Supabase PostgreSQL |
| Database access | Supabase Client |
| ORM (backend infrastructure) | SQLAlchemy |
| Database migrations | Alembic |
| API server | Uvicorn |
| Code quality | Ruff |
| Testing | pytest |
| Version control | Git and GitHub |

---

## Project Structure

```text
poc/
├── backend/
│   ├── app/
│   │   ├── db/
│   │   │   └── session.py
│   │   └── main.py
│   ├── migrations/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── README.md
│   └── test_db.py
│
├── frontend/
│   ├── sign-in.html
│   ├── sign-up.html
│   ├── dashboard.html
│   ├── profile.html
│   ├── js/
│   │   ├── api.js
│   │   ├── app.js
│   │   └── data.js
│   └── css/
│       └── styles.css
│
├── .gitignore
└── README.md
```

---

## Requirements

The following instructions primarily target Linux distributions such as Arch Linux, Ubuntu, and Debian.

Required software:

- Python 3.12 or later
- pip
- Git
- Node.js (if required by additional frontend development tools)
- A Supabase project

### Arch Linux

```bash
sudo pacman -S python python-pip git nodejs npm
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git nodejs npm
```

---

## Backend Setup

### 1. Navigate to the backend directory

```bash
cd backend
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Run the FastAPI development server

```bash
uvicorn app.main:app --reload
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

To stop the server, press `Ctrl + C`.

To deactivate the virtual environment:

```bash
deactivate
```

---

## Frontend Setup

The frontend is implemented using HTML, CSS, and JavaScript.

### 1. Configure Supabase

The frontend communicates directly with Supabase Auth through the Supabase JavaScript client.

Configure the following values in `frontend/js/api.js`:

```javascript
const SUPABASE_URL = "YOUR_SUPABASE_PROJECT_URL";
const SUPABASE_PUBLISHABLE_KEY = "YOUR_SUPABASE_PUBLISHABLE_KEY";
```

Use the project's Supabase URL and publishable key.

Do not place a Supabase secret key or `service_role` key in frontend code.

### 2. Start the frontend development server

Open another terminal at the project root:

```bash
cd poc
```

Start a local HTTP server:

```bash
python -m http.server 5500 --directory frontend
```

The frontend will be available at:

```text
http://127.0.0.1:5500
```

### 3. Access the application

Sign-up page:

```text
http://127.0.0.1:5500/sign-up.html
```

Sign-in page:

```text
http://127.0.0.1:5500/sign-in.html
```

Dashboard:

```text
http://127.0.0.1:5500/dashboard.html
```

The frontend should be accessed through the local HTTP server rather than opening HTML files directly using a `file://` URL.

---

## Running the Application

The frontend and backend must run in separate terminals.

### Terminal 1: Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

### Terminal 2: Frontend

```bash
cd poc
python -m http.server 5500 --directory frontend
```

The application can then be accessed through:

```text
http://127.0.0.1:5500
```

---

## API Documentation

FastAPI automatically generates interactive API documentation through Swagger UI.

Open:

```text
http://127.0.0.1:8000/docs
```

### Available Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Returns the API status |
| GET | `/health` | Checks backend availability |

### Example: Root Endpoint

Request:

```http
GET /
```

Expected response:

```json
{
  "message": "Yourin API is running"
}
```

### Example: Health Check

Request:

```http
GET /health
```

Expected response:

```json
{
  "status": "healthy"
}
```

---

## Authentication Architecture

Yourin uses Supabase Auth as its authentication provider.

Authentication responsibilities are separated from the FastAPI backend.

### Supabase Auth

Supabase manages:

- User registration.
- User login.
- Password management.
- Authentication sessions.
- User identity.

### Supabase Database

The planned `public.accounts` table stores application-specific account information associated with Supabase Auth users.

The table is intended to contain:

| Column | Description |
|---|---|
| `id` | References the corresponding Supabase Auth user ID |
| `username` | Unique application username |
| `created_at` | Account creation timestamp |
| `updated_at` | Last modification timestamp |

### FastAPI

FastAPI provides the backend infrastructure for application-specific API functionality.

It does not maintain an independent password database or authentication session system.

### Authentication Workflow

1. A user submits registration information through the frontend.
2. The frontend communicates with Supabase Auth.
3. Supabase creates the authenticated user.
4. The user signs in through Supabase Auth.
5. Supabase manages the user's authentication session.
6. The frontend accesses protected application pages according to authentication state.

---

## Development Tools

### Ruff

Ruff is used for Python linting and code formatting.

Install:

```bash
pip install ruff
```

Check code quality:

```bash
ruff check .
```

Automatically fix supported issues:

```bash
ruff check . --fix
```

Format Python files:

```bash
ruff format .
```

### pytest

pytest is used for automated Python testing.

Install:

```bash
pip install pytest
```

Run tests:

```bash
pytest
```

Run tests with more detailed output:

```bash
pytest -v
```

### Secret Scanning

Use Gitleaks to detect accidentally committed credentials, API keys, and other sensitive information.

Install Gitleaks using the official installation instructions:

https://github.com/gitleaks/gitleaks

Scan the repository:

```bash
gitleaks git .
```

You can also configure GitHub Secret Scanning and Push Protection in your repository settings if these features are available for your repository.

---

## Troubleshooting

### FastAPI cannot start

Ensure that:

- The virtual environment is activated.
- Dependencies are installed.
- The terminal is running from the `backend/` directory.
- The application entry point is `app.main:app`.

Run:

```bash
uvicorn app.main:app --reload
```

### Frontend cannot connect to FastAPI

Verify that:

- FastAPI is running at `http://127.0.0.1:8000`.
- The frontend is running at `http://127.0.0.1:5500`.
- The backend CORS configuration allows the frontend origin.

### Supabase authentication fails

Verify that:

- The Supabase project is active.
- The Project URL is correct.
- The publishable key is correct.
- Supabase Auth allows new user registration.
- Email confirmation settings are compatible with the application's username-based authentication approach.

### Python dependencies are missing

Activate the virtual environment and reinstall dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Security Notes

- Supabase Auth is responsible for password management and authentication sessions.
- Never store plaintext passwords in the application database or browser storage.
- Supabase publishable keys are designed for frontend use.
- Never expose Supabase secret keys or legacy `service_role` keys in frontend code.
- Enable Row Level Security (RLS) on tables containing user-specific information.
- Never commit database credentials, private API keys, or environment files containing secrets.
- Use HTTPS in production deployments.
- Backend endpoints that access protected resources must independently validate Supabase access tokens.
- Frontend authentication checks alone are insufficient to secure backend resources.
- This project is a proof of concept and requires further security review before production deployment.