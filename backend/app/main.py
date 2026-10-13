from fastapi import FastAPI

from app.routers import expenses, budgets, auth, analytics

from app.database import init_db


app = FastAPI(
    title="Expense Tracker API",
    description="Backend API for Expense Tracker",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {
        "message": "Expense Tracker API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


app.include_router(expenses.router)
app.include_router(budgets.router)
app.include_router(auth.router)
app.include_router(analytics.router)
