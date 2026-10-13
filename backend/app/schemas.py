from pydantic import BaseModel, Field, EmailStr, field_validator


# =========================================================
# USER REGISTRATION
# =========================================================

class UserCreate(BaseModel):

    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
    )

    email: EmailStr

    phone: str = Field(
        ...,
        min_length=10,
        max_length=15,
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    # -----------------------------------------------------
    # PHONE VALIDATION
    # -----------------------------------------------------

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):

        value = value.strip()

        if not value.replace("+", "").isdigit():

            raise ValueError(
                "Phone number must contain only digits and an optional +"
            )

        if value.count("+") > 1 or (
            "+" in value and not value.startswith("+")
        ):

            raise ValueError(
                "Invalid phone number format"
            )

        return value

    # -----------------------------------------------------
    # USERNAME VALIDATION
    # -----------------------------------------------------

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):

        value = value.strip()

        if len(value) < 3:

            raise ValueError(
                "Username must be at least 3 characters"
            )

        if len(value) > 30:

            raise ValueError(
                "Username must not exceed 30 characters"
            )

        return value

    # -----------------------------------------------------
    # PASSWORD VALIDATION
    # -----------------------------------------------------

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):

        if not any(
            char.isupper()
            for char in value
        ):

            raise ValueError(
                "Password must contain at least one uppercase letter"
            )

        if not any(
            char.islower()
            for char in value
        ):

            raise ValueError(
                "Password must contain at least one lowercase letter"
            )

        if not any(
            char.isdigit()
            for char in value
        ):

            raise ValueError(
                "Password must contain at least one digit"
            )

        if not any(
            not char.isalnum()
            for char in value
        ):

            raise ValueError(
                "Password must contain at least one special character"
            )

        return value


# =========================================================
# USER LOGIN
# =========================================================

class UserLogin(BaseModel):

    email: EmailStr
    password: str


# =========================================================
# USER RESPONSE
# =========================================================

class UserResponse(BaseModel):

    id: int
    username: str
    email: EmailStr
    phone: str


# =========================================================
# TOKEN RESPONSE
# =========================================================

class TokenResponse(BaseModel):

    access_token: str
    refresh_token: str
    token_type: str


# =========================================================
# REFRESH TOKEN REQUEST
# =========================================================

class RefreshTokenRequest(BaseModel):

    refresh_token: str

# =========================================================
# FORGOT PASSWORD
# =========================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# =========================================================
# RESET PASSWORD
# =========================================================

class ResetPasswordRequest(BaseModel):
    token: str = Field(
        ...,
        min_length=32,
        max_length=512,
    )

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):

        if not any(char.isupper() for char in value):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )

        if not any(char.islower() for char in value):
            raise ValueError(
                "Password must contain at least one lowercase letter"
            )

        if not any(char.isdigit() for char in value):
            raise ValueError(
                "Password must contain at least one digit"
            )

        if not any(not char.isalnum() for char in value):
            raise ValueError(
                "Password must contain at least one special character"
            )

        return value