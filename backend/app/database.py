import sqlite3
from pathlib import Path
from datetime import datetime, timezone


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = BASE_DIR / "expense_tracker.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    """Create and return a SQLite database connection."""

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    # Enable foreign-key support
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():
    """Create required database tables and perform migrations."""

    connection = get_connection()
    cursor = connection.cursor()

    # =====================================================
    # USERS TABLE
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    # =====================================================
    # PASSWORD RESET TOKENS TABLE
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # =====================================================
    # EXPENSES TABLE
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # =====================================================
    # EXPENSE TABLE MIGRATION
    # =====================================================

    cursor.execute("PRAGMA table_info(expenses)")

    expense_columns = [
        column["name"]
        for column in cursor.fetchall()
    ]

    if "user_id" not in expense_columns:

        cursor.execute("""
            ALTER TABLE expenses
            ADD COLUMN user_id INTEGER
        """)

    # =====================================================
    # BUDGET TABLE MIGRATION
    # =====================================================

    cursor.execute("PRAGMA table_info(budgets)")

    budget_table_exists = len(cursor.fetchall()) > 0

    if not budget_table_exists:

        # -----------------------------------------------
        # Create new user-specific budgets table
        # -----------------------------------------------

        cursor.execute("""
            CREATE TABLE budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                amount REAL NOT NULL,

                FOREIGN KEY (user_id)
                    REFERENCES users(id),

                UNIQUE(user_id, month)
            )
        """)

    else:

        # -----------------------------------------------
        # Check existing budget table structure
        # -----------------------------------------------

        cursor.execute("PRAGMA table_info(budgets)")

        budget_columns = [
            column["name"]
            for column in cursor.fetchall()
        ]

        # -----------------------------------------------
        # Old table does not have user_id
        # -----------------------------------------------

        if "user_id" not in budget_columns:

            # Get the first registered user.
            # Existing shared budgets will be assigned
            # to this user during migration.
            cursor.execute("""
                SELECT id
                FROM users
                ORDER BY id
                LIMIT 1
            """)

            first_user = cursor.fetchone()

            if first_user:

                first_user_id = first_user["id"]

                # ---------------------------------------
                # Rename old table
                # ---------------------------------------

                cursor.execute("""
                    ALTER TABLE budgets
                    RENAME TO budgets_old
                """)

                # ---------------------------------------
                # Create new table
                # ---------------------------------------

                cursor.execute("""
                    CREATE TABLE budgets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        month TEXT NOT NULL,
                        amount REAL NOT NULL,

                        FOREIGN KEY (user_id)
                            REFERENCES users(id),

                        UNIQUE(user_id, month)
                    )
                """)

                # ---------------------------------------
                # Move old budgets into new table
                # ---------------------------------------

                cursor.execute("""
                    INSERT INTO budgets (
                        user_id,
                        month,
                        amount
                    )
                    SELECT
                        ?,
                        month,
                        amount
                    FROM budgets_old
                """, (first_user_id,))

                # ---------------------------------------
                # Remove old table
                # ---------------------------------------

                cursor.execute("""
                    DROP TABLE budgets_old
                """)

            else:

                # No users exist yet.
                # Create the new table without migrating
                # any old budget rows.
                cursor.execute("""
                    DROP TABLE budgets
                """)

                cursor.execute("""
                    CREATE TABLE budgets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        month TEXT NOT NULL,
                        amount REAL NOT NULL,

                        FOREIGN KEY (user_id)
                            REFERENCES users(id),

                        UNIQUE(user_id, month)
                    )
                """)

        else:

            # -------------------------------------------
            # user_id already exists.
            #
            # We leave the table as-is if the application
            # is already using the user-specific structure.
            # -------------------------------------------

            pass

    connection.commit()
    connection.close()


# =========================================================
# EXPENSE FUNCTIONS
# =========================================================

def add_expense(
    user_id,
    name,
    amount,
    category,
    date,
):
    """Add a new expense for a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO expenses (
            user_id,
            name,
            amount,
            category,
            date
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        name,
        amount,
        category,
        date,
    ))

    connection.commit()

    expense_id = cursor.lastrowid

    connection.close()

    return expense_id


def get_expenses(user_id):
    """Return all expenses belonging to a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            amount,
            category,
            date
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
    """, (user_id,))

    expenses = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return expenses


def get_expense(
    user_id,
    expense_id,
):
    """Return one expense belonging to a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            amount,
            category,
            date
        FROM expenses
        WHERE id = ?
        AND user_id = ?
    """, (
        expense_id,
        user_id,
    ))

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None


def update_expense(
    user_id,
    expense_id,
    name,
    amount,
    category,
    date,
):
    """Update an expense belonging to a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE expenses
        SET
            name = ?,
            amount = ?,
            category = ?,
            date = ?
        WHERE id = ?
        AND user_id = ?
    """, (
        name,
        amount,
        category,
        date,
        expense_id,
        user_id,
    ))

    connection.commit()

    updated = cursor.rowcount > 0

    connection.close()

    return updated


def delete_expense(
    user_id,
    expense_id,
):
    """Delete an expense belonging to a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM expenses
        WHERE id = ?
        AND user_id = ?
    """, (
        expense_id,
        user_id,
    ))

    connection.commit()

    deleted = cursor.rowcount > 0

    connection.close()

    return deleted


# =========================================================
# BUDGET FUNCTIONS
# =========================================================

def set_budget(
    user_id,
    month,
    amount,
):
    """Create or update a monthly budget for a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO budgets (
            user_id,
            month,
            amount
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id, month)
        DO UPDATE SET
            amount = excluded.amount
    """, (
        user_id,
        month,
        amount,
    ))

    connection.commit()

    connection.close()


def get_budget(
    user_id,
    month,
):
    """Return the budget for a specific user and month."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT amount
        FROM budgets
        WHERE user_id = ?
        AND month = ?
    """, (
        user_id,
        month,
    ))

    row = cursor.fetchone()

    connection.close()

    return row["amount"] if row else 0.0


def delete_budget(
    user_id,
    month,
):
    """Delete a monthly budget belonging to a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM budgets
        WHERE user_id = ?
        AND month = ?
    """, (
        user_id,
        month,
    ))

    connection.commit()

    deleted = cursor.rowcount > 0

    connection.close()

    return deleted


# =========================================================
# USER FUNCTIONS
# =========================================================

def create_user(
    username,
    email,
    phone,
    password_hash,
):
    """Create a new user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO users (
            username,
            email,
            phone,
            password_hash
        )
        VALUES (?, ?, ?, ?)
    """, (
        username,
        email,
        phone,
        password_hash,
    ))

    connection.commit()

    user_id = cursor.lastrowid

    connection.close()

    return user_id


def get_user_by_email(email):
    """Return a user by email."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            username,
            email,
            phone,
            password_hash
        FROM users
        WHERE email = ?
    """, (email,))

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None


def get_user_by_id(user_id):
    """Return a user by ID."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            username,
            email,
            phone,
            password_hash
        FROM users
        WHERE id = ?
    """, (user_id,))

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None
# =========================================================
# ANALYTICS FUNCTIONS
# =========================================================

def get_expense_summary(user_id):
    """Return summary analytics for a specific user."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(amount), 0) AS total_spent,
            COALESCE(AVG(amount), 0) AS average_expense,
            COALESCE(MAX(amount), 0) AS highest_expense
        FROM expenses
        WHERE user_id = ?
    """, (user_id,))

    row = cursor.fetchone()

    cursor.execute("""
        SELECT
            category,
            SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
    """, (user_id,))

    top_category_row = cursor.fetchone()

    connection.close()

    return {
        "total_spent": float(row["total_spent"]),
        "average_expense": float(row["average_expense"]),
        "highest_expense": float(row["highest_expense"]),
        "top_category": (
            top_category_row["category"]
            if top_category_row
            else None
        ),
    }


def get_category_analytics(user_id):
    """Return total spending grouped by category."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            category,
            SUM(amount) AS total,
            COUNT(*) AS count
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
    """, (user_id,))

    results = [
        {
            "category": row["category"],
            "total": float(row["total"]),
            "count": int(row["count"]),
        }
        for row in cursor.fetchall()
    ]

    connection.close()

    return results


def get_monthly_analytics(user_id):
    """Return total spending grouped by month."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            substr(date, 1, 7) AS month,
            SUM(amount) AS total,
            COUNT(*) AS count
        FROM expenses
        WHERE user_id = ?
        GROUP BY substr(date, 1, 7)
        ORDER BY month ASC
    """, (user_id,))

    results = [
        {
            "month": row["month"],
            "total": float(row["total"]),
            "count": int(row["count"]),
        }
        for row in cursor.fetchall()
    ]

    connection.close()

    return results

def create_password_reset_token(
    user_id: int,
    token_hash: str,
    expires_at: str,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Invalidate previous unused reset tokens
        cursor.execute("""
            UPDATE password_reset_tokens
            SET used = 1
            WHERE user_id = ? AND used = 0
        """, (user_id,))

        cursor.execute("""
            INSERT INTO password_reset_tokens
                (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token_hash, expires_at))

        connection.commit()

    finally:
        connection.close()


def get_password_reset_token(token_hash: str):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id, user_id, expires_at, used
            FROM password_reset_tokens
            WHERE token_hash = ?
        """, (token_hash,))

        row = cursor.fetchone()
        return dict(row) if row else None

    finally:
        connection.close()


def consume_password_reset_token(
    token_hash: str,
    user_id: int,
    password_hash: str,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT id, expires_at, used
            FROM password_reset_tokens
            WHERE token_hash = ? AND user_id = ?
        """, (token_hash, user_id))

        row = cursor.fetchone()

        if not row or row["used"]:
            connection.rollback()
            return False

        expires_at = datetime.fromisoformat(
            row["expires_at"]
        )

        if expires_at <= datetime.now(timezone.utc):
            connection.rollback()
            return False

        cursor.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
        """, (password_hash, user_id))

        cursor.execute("""
            UPDATE password_reset_tokens
            SET used = 1
            WHERE id = ? AND used = 0
        """, (row["id"],))

        if cursor.rowcount != 1:
            connection.rollback()
            return False

        connection.commit()
        return True

    finally:
        connection.close()
