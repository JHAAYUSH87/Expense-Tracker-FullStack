from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.database import (
    set_budget,
    get_budget,
    delete_budget,
)

from app.dependencies import get_current_user


router = APIRouter(
    prefix="/budget",
    tags=["Budget"],
)


# =========================================================
# REQUEST / RESPONSE MODELS
# =========================================================

class BudgetCreate(BaseModel):

    month: str = Field(
        ...,
        min_length=1,
    )

    amount: float = Field(
        ...,
        gt=0,
    )


class BudgetResponse(BaseModel):

    month: str
    amount: float


# =========================================================
# CREATE / UPDATE BUDGET
# =========================================================

@router.post(
    "/",
    response_model=BudgetResponse,
)
def create_or_update_budget(
    budget: BudgetCreate,
    current_user=Depends(get_current_user),
):

    set_budget(
        current_user["id"],
        budget.month,
        budget.amount,
    )

    return {
        "month": budget.month,
        "amount": budget.amount,
    }


# =========================================================
# GET MONTHLY BUDGET
# =========================================================

@router.get(
    "/{month}",
    response_model=BudgetResponse,
)
def read_budget(
    month: str,
    current_user=Depends(get_current_user),
):

    amount = get_budget(
        current_user["id"],
        month,
    )

    # Return ₹0 when no budget exists.
    # This allows the dashboard to load normally.

    return {
        "month": month,
        "amount": amount,
    }


# =========================================================
# DELETE MONTHLY BUDGET
# =========================================================

@router.delete(
    "/{month}",
)
def remove_budget(
    month: str,
    current_user=Depends(get_current_user),
):

    deleted = delete_budget(
        current_user["id"],
        month,
    )

    if not deleted:

        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    return {
        "message": "Budget deleted successfully",
    }