from fastapi import APIRouter, Depends

from app.database import (
    get_expense_summary,
    get_category_analytics,
    get_monthly_analytics,
)

from app.dependencies import get_current_user


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


# =========================================================
# EXPENSE SUMMARY
# =========================================================

@router.get("/summary")
def expense_summary(
    current_user=Depends(get_current_user),
):
    return get_expense_summary(
        current_user["id"]
    )


# =========================================================
# CATEGORY ANALYTICS
# =========================================================

@router.get("/categories")
def category_analytics(
    current_user=Depends(get_current_user),
):
    return get_category_analytics(
        current_user["id"]
    )


# =========================================================
# MONTHLY ANALYTICS
# =========================================================

@router.get("/monthly")
def monthly_analytics(
    current_user=Depends(get_current_user),
):
    return get_monthly_analytics(
        current_user["id"]
    )
