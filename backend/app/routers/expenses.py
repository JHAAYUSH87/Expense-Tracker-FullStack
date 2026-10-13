from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.database import (
    add_expense,
    get_expenses,
    get_expense,
    update_expense,
    delete_expense,
)

from app.dependencies import get_current_user


router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"],
)


# =========================================================
# SCHEMAS
# =========================================================

class ExpenseCreate(BaseModel):

    name: str = Field(
        ...,
        min_length=1,
    )

    amount: float = Field(
        ...,
        gt=0,
    )

    category: str = Field(
        ...,
        min_length=1,
    )

    date: str = Field(
        ...,
        min_length=1,
    )


class ExpenseResponse(ExpenseCreate):

    id: int


# =========================================================
# CREATE EXPENSE
# =========================================================

@router.post(
    "/",
    response_model=ExpenseResponse,
)
def create_expense(
    expense: ExpenseCreate,
    current_user=Depends(get_current_user),
):

    expense_id = add_expense(
        current_user["id"],
        expense.name,
        expense.amount,
        expense.category,
        expense.date,
    )

    return {
        "id": expense_id,
        "name": expense.name,
        "amount": expense.amount,
        "category": expense.category,
        "date": expense.date,
    }


# =========================================================
# GET ALL EXPENSES
# =========================================================

@router.get(
    "/",
    response_model=list[ExpenseResponse],
)
def read_expenses(
    current_user=Depends(get_current_user),
):

    return get_expenses(
        current_user["id"]
    )


# =========================================================
# GET SINGLE EXPENSE
# =========================================================

@router.get(
    "/{expense_id}",
    response_model=ExpenseResponse,
)
def read_expense(
    expense_id: int,
    current_user=Depends(get_current_user),
):

    expense = get_expense(
        current_user["id"],
        expense_id,
    )

    if expense is None:

        raise HTTPException(
            status_code=404,
            detail="Expense not found",
        )

    return expense


# =========================================================
# UPDATE EXPENSE
# =========================================================

@router.put(
    "/{expense_id}",
    response_model=ExpenseResponse,
)
def edit_expense(
    expense_id: int,
    expense: ExpenseCreate,
    current_user=Depends(get_current_user),
):

    updated = update_expense(
        current_user["id"],
        expense_id,
        expense.name,
        expense.amount,
        expense.category,
        expense.date,
    )

    if not updated:

        raise HTTPException(
            status_code=404,
            detail="Expense not found",
        )

    return {
        "id": expense_id,
        "name": expense.name,
        "amount": expense.amount,
        "category": expense.category,
        "date": expense.date,
    }


# =========================================================
# DELETE EXPENSE
# =========================================================

@router.delete(
    "/{expense_id}"
)
def remove_expense(
    expense_id: int,
    current_user=Depends(get_current_user),
):

    deleted = delete_expense(
        current_user["id"],
        expense_id,
    )

    if not deleted:

        raise HTTPException(
            status_code=404,
            detail="Expense not found",
        )

    return {
        "message": "Expense deleted successfully"
    }