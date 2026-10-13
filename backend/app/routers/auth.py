import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from jose import JWTError, jwt

from app.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.database import (
    create_user,
    get_user_by_email,
    create_password_reset_token,
    get_password_reset_token,
    consume_password_reset_token,
)
from app.auth import hash_password, verify_password
from app.config import (
    SECRET_KEY,
    REFRESH_SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

# This file is backend/app/routers/auth.py.
# parents[0] = routers, [1] = app, [2] = backend, [3] = project root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


def _load_project_env(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding existing environment variables."""
    if not path.is_file():
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(path, override=False)
        return
    except ImportError:
        # Fallback if python-dotenv is not installed.
        pass

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0:1] in ("'", '"') and value[-1:] == value[0]:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


_load_project_env(ENV_FILE)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Email configuration is read after loading the project-root .env file.
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "").strip()
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
APP_PUBLIC_URL = os.getenv(
    "APP_PUBLIC_URL",
    "http://127.0.0.1:8000",
).rstrip("/")


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def send_reset_email(email: str, reset_link: str) -> None:
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise RuntimeError(
            "SMTP_EMAIL and SMTP_APP_PASSWORD are not configured in the project .env file."
        )

    message = EmailMessage()
    message["Subject"] = "Reset your Expense Tracker password"
    message["From"] = SMTP_EMAIL
    message["To"] = email
    message.set_content(
        "We received a request to reset your Expense Tracker password.\n\n"
        f"Open this link to choose a new password:\n{reset_link}\n\n"
        "This link expires in 20 minutes and can only be used once.\n"
        "If you did not request this, you can ignore this email."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(message)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(user: UserCreate):
    existing_user = get_user_by_email(str(user.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    password_hash = hash_password(user.password)
    try:
        user_id = create_user(
            username=user.username,
            email=str(user.email),
            phone=user.phone,
            password_hash=password_hash,
        )
    except Exception as error:
        # Do not return internal database details to clients.
        print("Registration failed:", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username, email, or phone number may already be registered.",
        ) from error

    return {
        "id": user_id,
        "username": user.username,
        "email": str(user.email),
        "phone": user.phone,
    }


@router.post("/login", response_model=TokenResponse)
def login_user(user: UserLogin):
    existing_user = get_user_by_email(str(user.email))
    if not existing_user or not verify_password(
        user.password,
        existing_user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_id = existing_user["id"]
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(data: RefreshTokenRequest):
    try:
        payload = jwt.decode(
            data.refresh_token,
            REFRESH_SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        subject = payload.get("sub")
        if not subject or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        user_id = int(subject)
    except (JWTError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from error

    # Preserve the existing refresh-token behaviour: return the same refresh token.
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": data.refresh_token,
        "token_type": "bearer",
    }


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    # Same response for existing and non-existing accounts to reduce account enumeration.
    generic_response = {
        "message": (
            "If an account exists for this email, "
            "password reset instructions will be sent."
        )
    }

    user = get_user_by_email(str(data.email))
    if not user:
        return generic_response

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=20)
    ).isoformat()
    reset_link = (
        f"{APP_PUBLIC_URL}/auth/reset-password-page"
        f"?token={quote(raw_token)}"
    )

    try:
        # Store the hashed token before sending the email to avoid a race if
        # the recipient opens the message immediately.
        create_password_reset_token(
            user_id=user["id"],
            token_hash=token_hash,
            expires_at=expires_at,
        )
        send_reset_email(str(data.email), reset_link)
    except Exception as error:
        # Never log the raw reset token or SMTP credentials.
        print("Password reset email could not be sent:", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email could not be sent. Please try again later.",
        ) from error

    return generic_response


@router.get("/reset-password-page", response_class=HTMLResponse)
def reset_password_page(token: str):
    # token_urlsafe tokens contain URL-safe characters; HTML-escape defensively.
    safe_token = (
        token.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reset Password - Expense Tracker</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 420px; margin: 60px auto;
       padding: 20px; background: #f5f6fa; color: #202124; }}
main {{ background: white; padding: 24px; border-radius: 14px; }}
input, button {{ box-sizing: border-box; width: 100%; padding: 12px; margin-top: 12px; }}
button {{ cursor: pointer; }}
#message {{ white-space: pre-wrap; }}
</style>
</head>
<body>
<main>
<h2>Reset your password</h2>
<p>Choose a new password for your Expense Tracker account.</p>
<form id="reset-form">
<input id="password" type="password" minlength="8" maxlength="128"
       autocomplete="new-password" placeholder="New password" required>
<input id="confirm" type="password" minlength="8" maxlength="128"
       autocomplete="new-password" placeholder="Confirm new password" required>
<button id="submit" type="submit">Update password</button>
</form>
<p id="message" role="status"></p>
</main>
<script>
const resetToken = "{safe_token}";
const form = document.getElementById("reset-form");
const message = document.getElementById("message");
const button = document.getElementById("submit");

form.addEventListener("submit", async (event) => {{
    event.preventDefault();
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirm").value;

    if (password !== confirmPassword) {{
        message.textContent = "Passwords do not match.";
        return;
    }}

    button.disabled = true;
    message.textContent = "Updating password...";
    try {{
        const response = await fetch("/auth/reset-password", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{
                token: resetToken,
                new_password: password
            }})
        }});
        const result = await response.json();
        if (!response.ok) {{
            throw new Error(result.detail || "Unable to reset password.");
        }}
        form.remove();
        message.textContent =
            "Password updated successfully. You can now return to Expense Tracker and log in.";
    }} catch (error) {{
        message.textContent = error.message || "Unable to reset password.";
        button.disabled = false;
    }}
}});
</script>
</body>
</html>"""

    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest):
    token_hash = hashlib.sha256(data.token.encode("utf-8")).hexdigest()
    reset_record = get_password_reset_token(token_hash)

    if not reset_record or reset_record["used"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link is invalid, expired, or already used.",
        )

    new_password_hash = hash_password(data.new_password)
    # This database helper must check expiry and mark the token used in a
    # transaction together with the password update.
    success = consume_password_reset_token(
        token_hash=token_hash,
        user_id=reset_record["user_id"],
        password_hash=new_password_hash,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link is invalid, expired, or already used.",
        )

    return {"message": "Password reset successful. Please log in."}
