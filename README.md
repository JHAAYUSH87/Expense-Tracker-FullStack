# Expense Tracker

A full-stack personal expense management application built with Python, Flet, FastAPI, and SQLite.

## Features

- User registration and login
- JWT-based authentication
- Email-based password reset
- Add, view, edit, and delete expenses
- Expense categories and search
- Budget management
- Spending analytics
- SQLite data persistence
- FastAPI interactive documentation

## Tech Stack

- **Frontend:** Python, Flet, Requests
- **Backend:** Python, FastAPI, Uvicorn, Pydantic
- **Database:** SQLite
- **Authentication:** JWT
- **Email:** SMTP

## Project Structure

- `backend/` — FastAPI application, API routes, authentication, and database logic
- `frontend/` — Flet user interface
- `.gitignore` — Excludes secrets, databases, and local backup files

## Run Locally

### 1. Configure environment variables

Create a `.env` file in the project root with unique `SECRET_KEY` and `REFRESH_SECRET_KEY` values, plus the SMTP settings required for password-reset emails.

Never commit `.env` or share real credentials.

### 2. Start the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API documentation: http://127.0.0.1:8000/docs

### 3. Start the frontend

Open a second terminal:

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The current frontend uses `http://127.0.0.1:8000` as its API URL. Remote deployment requires configuring the appropriate backend URL.

## Security Notes

- Do not commit environment files, credentials, local databases, or backups.
- Use unique JWT secrets for each environment.
- Configure SMTP credentials locally.
- Review security and deployment settings before production use.

## Screenshots

Screenshots of the dashboard, expenses, budgets, and login screens can be added here.

## Project Status

Local backend startup and login have been tested. Clean-installation and production-deployment checks remain separate tasks.

## License

No license has been selected yet. All rights remain with the author unless a license is added.
