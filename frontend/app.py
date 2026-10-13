import asyncio
import base64
import math
import re

from datetime import datetime



import flet as ft

import requests





# =============================================================

# CONFIGURATION

# =============================================================



API_URL = "http://127.0.0.1:8000"



REMEMBER_TOKEN_KEY = "expense_tracker_remember_token"
REMEMBER_EMAIL_KEY = "expense_tracker_remember_email"
REMEMBER_REFRESH_TOKEN_KEY = "expense_tracker_remember_refresh_token"
YEARLY_BUDGET_KEY_PREFIX = "expense_tracker_yearly_budget_"
THEME_MODE_KEY = "expense_tracker_theme_mode"


CATEGORIES = [

    "Food",

    "Home",

    "Transport",

    "Shopping",

    "Health",

    "Education",

    "Entertainment",

    "Work",

    "Bills",

    "Misc",

]


# =============================================================
# VISUAL COLOUR PALETTE
# UI polish: consistent primary actions and clearly destructive actions
# =============================================================

COLOR_PRIMARY = "#6366F1"       # Indigo
COLOR_SUCCESS = "#10B981"       # Emerald
COLOR_WARNING = "#F59E0B"       # Amber
COLOR_DANGER = "#EF4444"        # Red
COLOR_DAILY_SPENDING = "#06B6D4"  # Cyan

CATEGORY_COLORS = {
    "Food": "#F59E0B",
    "Home": "#10B981",
    "Transport": "#06B6D4",
    "Shopping": "#6366F1",
    "Health": "#EF4444",
    "Education": "#8B5CF6",
    "Entertainment": "#EC4899",
    "Work": "#3B82F6",
    "Bills": "#14B8A6",
    "Misc": "#9CA3AF",
}



REQUEST_TIMEOUT = 5

UNDO_DURATION_MS = 5000

UNDO_DURATION_SECONDS = 5





# =============================================================

# MAIN APPLICATION

# =============================================================



async def main(page: ft.Page):

    # =========================================================

    # PAGE SETTINGS

    # =========================================================



    page.title = "Expense Tracker"

    page.window.width = 1150

    page.window.height = 800

    page.padding = 25

    page.scroll = ft.ScrollMode.AUTO



    # SharedPreferences stores the user's theme choice across launches.
    prefs = ft.SharedPreferences()

    saved_theme_mode = await prefs.get(THEME_MODE_KEY)
    theme_mode = (
        ft.ThemeMode.DARK
        if saved_theme_mode == "dark"
        else ft.ThemeMode.LIGHT
    )
    page.theme_mode = theme_mode
    page.theme = ft.Theme(color_scheme_seed=COLOR_PRIMARY)
    # Flet 1.0.3 infers dark appearance from page.theme_mode;
    # Theme() does not accept a brightness argument.
    page.dark_theme = ft.Theme(
        color_scheme_seed=COLOR_PRIMARY,
    )

    theme_buttons = []

    async def toggle_theme(e):
        nonlocal theme_mode

        theme_mode = (
            ft.ThemeMode.DARK
            if theme_mode == ft.ThemeMode.LIGHT
            else ft.ThemeMode.LIGHT
        )
        page.theme_mode = theme_mode
        await prefs.set(
            THEME_MODE_KEY,
            "dark" if theme_mode == ft.ThemeMode.DARK else "light",
        )

        for button in theme_buttons:
            button.icon = (
                ft.Icons.LIGHT_MODE
                if theme_mode == ft.ThemeMode.DARK
                else ft.Icons.DARK_MODE
            )
            button.tooltip = (
                "Switch to light mode"
                if theme_mode == ft.ThemeMode.DARK
                else "Switch to dark mode"
            )

        page.update()

    def make_theme_button():
        button = ft.IconButton(
            icon=(
                ft.Icons.LIGHT_MODE
                if theme_mode == ft.ThemeMode.DARK
                else ft.Icons.DARK_MODE
            ),
            tooltip=(
                "Switch to light mode"
                if theme_mode == ft.ThemeMode.DARK
                else "Switch to dark mode"
            ),
            on_click=toggle_theme,
        )
        theme_buttons.append(button)
        return button

    # =========================================================

    # GLOBAL STATE

    # =========================================================



    access_token = None

    refresh_token = None

    current_user = None

    all_expenses = []



    # =========================================================

    # GENERAL HELPERS

    # =========================================================



    def money(value):

        try:

            return f"₹{float(value):,.2f}"

        except (ValueError, TypeError):

            return "₹0.00"



    def current_month():

        return datetime.now().strftime("%Y-%m")



    def current_year():

        return datetime.now().year



    def today():

        return datetime.now().strftime("%Y-%m-%d")



    def valid_date(value):

        try:

            datetime.strptime(str(value), "%Y-%m-%d")

            return True

        except (ValueError, TypeError):

            return False



    def parse_positive_amount(value):

        try:

            amount = float(str(value).strip())

            if amount <= 0:

                return None

            return amount

        except (ValueError, TypeError):

            return None



    def valid_email(value):

        email = str(value or "").strip()

        return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email))



    # =========================================================
    # AUTHORIZATION HEADER
    # =========================================================

    def auth_headers():

        if not access_token:
            return {}

        return {
            "Authorization": f"Bearer {access_token}"
        }


    # =========================================================
    # API REQUEST
    # =========================================================

    async def api_request(method, path, **kwargs):
        """
        Send an API request.

        If the access token has expired:
        1. Use the refresh token.
        2. Get a new access token.
        3. Retry the original request once.

        If refresh fails, return the original 401 response.
        """

        nonlocal access_token
        nonlocal refresh_token

        headers = kwargs.pop("headers", None)

        # If caller did not provide headers,
        # automatically use the current access token.
        if headers is None:
            headers = auth_headers()

        response = await asyncio.to_thread(
            requests.request,
            method,
            f"{API_URL}{path}",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )

        # =====================================================
        # ACCESS TOKEN EXPIRED
        # =====================================================

        if (
            response.status_code == 401
            and refresh_token
            and not path.startswith("/auth/")
        ):

            try:

                refresh_response = await asyncio.to_thread(
                    requests.post,
                    f"{API_URL}/auth/refresh",
                    json={
                        "refresh_token": refresh_token
                    },
                    timeout=REQUEST_TIMEOUT,
                )

                # =================================================
                # REFRESH SUCCESS
                # =================================================

                if refresh_response.status_code == 200:

                    data = refresh_response.json()

                    new_access_token = data.get(
                        "access_token"
                    )

                    new_refresh_token = data.get(
                        "refresh_token"
                    )

                    if new_access_token:

                        access_token = new_access_token

                        # Backend may rotate refresh tokens.
                        # If it sends a new one, keep it.
                        if new_refresh_token:
                            refresh_token = new_refresh_token

                        # -------------------------------------------------
                        # SAVE UPDATED TOKENS IF REMEMBER ME IS ACTIVE
                        # -------------------------------------------------

                        saved_refresh_token = await prefs.get(
                            REMEMBER_REFRESH_TOKEN_KEY
                        )

                        if saved_refresh_token:

                            await prefs.set(
                                REMEMBER_TOKEN_KEY,
                                access_token
                            )

                            await prefs.set(
                                REMEMBER_REFRESH_TOKEN_KEY,
                                refresh_token
                            )

                        # -------------------------------------------------
                        # RETRY ORIGINAL REQUEST
                        # -------------------------------------------------

                        retry_headers = dict(
                            headers or {}
                        )

                        retry_headers["Authorization"] = (
                            f"Bearer {access_token}"
                        )

                        response = await asyncio.to_thread(
                            requests.request,
                            method,
                            f"{API_URL}{path}",
                            headers=retry_headers,
                            timeout=REQUEST_TIMEOUT,
                            **kwargs,
                        )

                        return response

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ):

                # Do not immediately force logout
                # if the backend is temporarily unavailable.
                pass

            except Exception as error:

                print(
                    "Token refresh error:",
                    error,
                )

        return response


    # =========================================================
    # RESPONSE ERROR HANDLER
    # =========================================================

    def response_detail(response, fallback):
        """
        Convert backend errors into clean
        user-friendly messages.
        """

        status_code = response.status_code

        # Authentication errors
        if status_code == 401:
            return "Invalid email or password."

        # Permission / access errors
        if status_code == 403:
            return (
                "You do not have permission "
                "to perform this action."
            )

        # Resource not found
        if status_code == 404:
            return (
                "The requested item was not found."
            )

        # Duplicate data
        if status_code == 409:
            return (
                "Email, username, or phone "
                "number already exists."
            )

        # Validation errors
        if status_code == 422:

            try:

                data = response.json()

                details = data.get(
                    "detail",
                    []
                )

                if (
                    isinstance(details, list)
                    and details
                ):

                    first_error = details[0]

                    message = first_error.get(
                        "msg",
                        ""
                    )

                    message = str(message)

                    message = message.replace(
                        "Value error, ",
                        ""
                    )

                    return message

                if isinstance(details, str):
                    return details

            except Exception:
                pass

            return (
                "Please check your input "
                "and try again."
            )

        # Server errors
        if status_code >= 500:
            return (
                "Server error. "
                "Please try again later."
            )

        # Other backend errors
        try:

            data = response.json()

            detail = data.get(
                "detail"
            )

            if isinstance(detail, str):
                return detail

        except Exception:
            pass

        return fallback


    # =========================================================
    # SHOW MESSAGE
    # =========================================================

    def show_message(text):

        # Consistent, color-coded feedback:
        # green = success, red = error, indigo = neutral/information.
        message_text = str(text)
        lowered = message_text.lower()

        error_markers = (
            "❌",
            "failed",
            "could not",
            "invalid",
            "error",
            "timed out",
            "timeout",
            "not found",
        )
        success_markers = (
            "✓",
            "success",
            "saved",
            "updated",
            "restored",
            "removed",
            "deleted",
            "added",
        )

        if any(marker in lowered for marker in error_markers):
            message_color = COLOR_DANGER
        elif any(marker in lowered for marker in success_markers) or "✓" in message_text:
            message_color = COLOR_SUCCESS
        else:
            message_color = COLOR_PRIMARY

        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(
                    message_text,
                    color=ft.Colors.WHITE,
                ),
                bgcolor=message_color,
                duration=3000,
            )
        )


    # =========================================================
    # SESSION EXPIRATION
    # =========================================================

    async def handle_unauthorized():

        nonlocal access_token
        nonlocal refresh_token
        nonlocal current_user

        # =====================================================
        # CLEAR AUTH STATE
        # =====================================================

        access_token = None
        refresh_token = None
        current_user = None

        # =====================================================
        # CLEAR SAVED SESSION
        # =====================================================

        await prefs.remove(
            REMEMBER_TOKEN_KEY
        )

        await prefs.remove(
            REMEMBER_REFRESH_TOKEN_KEY
        )

        await prefs.remove(
            REMEMBER_EMAIL_KEY
        )

        # =====================================================
        # RETURN TO LOGIN
        # =====================================================

        await show_login(
            "Your session has expired. "
            "Please login again."
        )


    # =========================================================
    # LOGIN SCREEN
    # =========================================================

    # =========================================================

    # LOGIN SCREEN

    # =========================================================



    async def show_login(message=""):

        page.controls.clear()
        theme_buttons.clear()

        page.title = "Expense Tracker - Login"



        saved_email = await prefs.get(REMEMBER_EMAIL_KEY)



        login_email = ft.TextField(

            label="Email",

            hint_text="Enter your email",

            value=saved_email or "",

            width=400,

            autofocus=True,

        )



        login_password = ft.TextField(

            label="Password",

            hint_text="Enter your password",

            password=True,

            can_reveal_password=True,

            width=400,

        )



        remember_me = ft.Checkbox(

            label="Remember me",

            value=bool(saved_email),

        )



        login_message = ft.Text(

            message,

            color=ft.Colors.RED,

            text_align=ft.TextAlign.CENTER,

        )



        login_button = ft.Button(

            content="Login",

            icon=ft.Icons.LOGIN,
            width=400,

        )



        async def login(e):

            nonlocal access_token, refresh_token, current_user



            email = (login_email.value or "").strip()

            password = login_password.value or ""

            login_message.value = ""



            if not email:

                login_message.value = "Please enter your email."

                page.update()

                return



            if not valid_email(email):

                login_message.value = "Please enter a valid email address."

                page.update()

                return



            if not password:

                login_message.value = "Please enter your password."

                page.update()

                return





            login_button.disabled = True
            login_button.content = "Logging in..."
            login_button.icon = ft.Icons.HOURGLASS_TOP
            login_message.value = "Please wait..."

            page.update()




            try:

                response = await api_request(

                    "POST",

                    "/auth/login",

                    json={"email": email, "password": password},

                    headers={},

                )



                if response.status_code == 200:

                    data = response.json()

                    token = data.get(
                        "access_token"
                    )

                    new_refresh_token = data.get(
                        "refresh_token"
                    )

                    # =================================================
                    # VALIDATE TOKENS
                    # =================================================

                    if not token:

                        login_message.value = (
                            "Login failed: "
                            "No access token received."
                        )

                        login_button.disabled = False
                        login_button.content = "Login"
                        login_button.icon = ft.Icons.LOGIN

                        page.update()

                        return

                    if not new_refresh_token:

                        login_message.value = (
                            "Login failed: "
                            "No refresh token received."
                        )

                        login_button.disabled = False
                        login_button.content = "Login"
                        login_button.icon = ft.Icons.LOGIN

                        page.update()

                        return

                    # =================================================
                    # SET CURRENT SESSION
                    # =================================================

                    access_token = token
                    refresh_token = new_refresh_token
                    current_user = email

                    # =================================================
                    # REMEMBER ME
                    # =================================================

                    if remember_me.value:

                        await prefs.set(
                            REMEMBER_EMAIL_KEY,
                            email
                        )

                        await prefs.set(
                            REMEMBER_TOKEN_KEY,
                            access_token
                        )

                        await prefs.set(
                            REMEMBER_REFRESH_TOKEN_KEY,
                            refresh_token
                        )

                    else:

                        await prefs.remove(
                            REMEMBER_EMAIL_KEY
                        )

                        await prefs.remove(
                            REMEMBER_TOKEN_KEY
                        )

                        await prefs.remove(
                            REMEMBER_REFRESH_TOKEN_KEY
                        )

                    # =================================================
                    # OPEN DASHBOARD
                    # =================================================

                    await show_dashboard()

                    return


                if response.status_code in (400, 401, 403):

                    login_message.value = "Invalid email or password."

                else:

                    login_message.value = response_detail(

                        response,

                        f"Login failed ({response.status_code}).",

                    )



            except requests.exceptions.ConnectionError:

                login_message.value = "Could not connect to backend ❌"

            except requests.exceptions.Timeout:

                login_message.value = "Login request timed out ❌"

            except Exception as error:

                login_message.value = "Login error ❌"

                print("Login error:", error)



            login_button.disabled = False

            page.update()



        login_button.on_click = login
        async def open_register(e):
            await show_register()


        register_button = ft.TextButton(
            "Create a new account",
            on_click=open_register,
        )



        page.add(

            ft.Container(

                alignment=ft.Alignment.CENTER,

                padding=30,

                content=ft.Column(

                    [

                        ft.Row(
                            [make_theme_button()],
                            alignment=ft.MainAxisAlignment.END,
                            width=450,
                        ),

                        ft.Text(

                            "Expense Tracker",

                            size=38,

                            weight=ft.FontWeight.BOLD,

                            text_align=ft.TextAlign.CENTER,

                        ),

                        ft.Text(

                            "Login to manage your expenses",

                            size=18,

                            text_align=ft.TextAlign.CENTER,

                        ),

                        ft.Container(height=25),

                        login_email,

                        login_password,

                        ft.Container(

                            content=remember_me,

                            width=400,

                        ),

                        login_message,

                        login_button,
                        register_button,

                    ],

                    width=450,

                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,

                    spacing=15,

                ),

            )

        )



        page.update()


    # =========================================================
    # REGISTER SCREEN
    # =========================================================

    async def show_register(message=""):

        page.controls.clear()
        theme_buttons.clear()

        page.title = "Expense Tracker - Create Account"

        register_username = ft.TextField(
            label="Username",
            hint_text="Enter your username",
            width=400,
        )

        register_email = ft.TextField(
            label="Email",
            hint_text="Enter your email",
            width=400,
        )

        register_phone = ft.TextField(
            label="Phone",
            hint_text="e.g. +919876543210",
            width=400,
        )

        register_password = ft.TextField(
            label="Password",
            hint_text="Create a strong password",
            password=True,
            can_reveal_password=True,
            width=400,
        )

        register_confirm_password = ft.TextField(
            label="Confirm Password",
            hint_text="Re-enter your password",
            password=True,
            can_reveal_password=True,
            width=400,
        )

        register_message = ft.Text(
            message,
            color=ft.Colors.RED,
            text_align=ft.TextAlign.CENTER,
        )

        register_button = ft.Button(
            content="Create Account",
            icon=ft.Icons.PERSON_ADD,
            width=400,
        )

        async def register(e):

            register_message.value = ""

            username = (
                register_username.value or ""
            ).strip()

            email = (
                register_email.value or ""
            ).strip()

            phone = (
                register_phone.value or ""
            ).strip()

            password = (
                register_password.value or ""
            )

            confirm_password = (
                register_confirm_password.value or ""
            )

            if not username:
                register_message.value = (
                    "Please enter your username."
                )
                page.update()
                return

            if not email:
                register_message.value = (
                    "Please enter your email."
                )
                page.update()
                return

            if not valid_email(email):
                register_message.value = (
                    "Please enter a valid email address."
                )
                page.update()
                return

            if not phone:
                register_message.value = (
                    "Please enter your phone number."
                )
                page.update()
                return

            if not password:
                register_message.value = (
                    "Please enter your password."
                )
                page.update()
                return

            if password != confirm_password:
                register_message.value = (
                    "Passwords do not match."
                )
                page.update()
                return

            register_button.disabled = True
            register_button.content = "Creating account..."
            register_button.icon = ft.Icons.HOURGLASS_TOP

            register_message.value = "Please wait..."

            page.update()

            try:

                response = await api_request(
                    "POST",
                    "/auth/register",
                    json={
                        "username": username,
                        "email": email,
                        "phone": phone,
                        "password": password,
                    },
                    headers={},
                )

                if response.status_code in (200, 201):

                    await show_login(
                        "Account created successfully. Please login."
                    )

                    return

                register_message.value = response_detail(
                    response,
                    "Registration failed.",
                )

            except requests.exceptions.ConnectionError:

                register_message.value = (
                    "Could not connect to backend ❌"
                )

            except requests.exceptions.Timeout:

                register_message.value = (
                    "Registration request timed out ❌"
                )

            except Exception as error:

                register_message.value = (
                    "Registration error ❌"
                )

                print(
                    "Registration error:",
                    error,
                )

            register_button.disabled = False
            register_button.content = "Create Account"
            register_button.icon = ft.Icons.PERSON_ADD

            page.update()

        register_button.on_click = register

        back_to_login_button = ft.TextButton(
            "Already have an account? Login",
            on_click=lambda e: show_login(),
        )

        page.add(

            ft.Container(

                expand=True,

                alignment=ft.Alignment.CENTER,

                content=ft.Column(

                    [

                        ft.Row(
                            [make_theme_button()],
                            alignment=ft.MainAxisAlignment.END,
                            width=450,
                        ),

                        ft.Text(
                            "Create Account",
                            size=34,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),

                        ft.Text(
                            "Create your Expense Tracker account",
                            size=16,
                            text_align=ft.TextAlign.CENTER,
                        ),

                        ft.Container(height=15),

                        register_username,
                        register_email,
                        register_phone,
                        register_password,
                        register_confirm_password,

                        register_message,

                        register_button,

                        back_to_login_button,

                    ],

                    horizontal_alignment=(
                        ft.CrossAxisAlignment.CENTER
                    ),

                    spacing=12,

                    tight=True,

                ),

            )

        )

        page.update()





    # =========================================================

    # DASHBOARD

    # =========================================================



    async def show_dashboard():

        page.controls.clear()
        theme_buttons.clear()

        page.title = "Expense Tracker"



        # =====================================================

        # DASHBOARD CONTROLS

        # =====================================================



        status = ft.Text("Backend: Checking...", size=16)



        total_value = ft.Text(

            "₹0.00", size=28, weight=ft.FontWeight.BOLD

        )

        monthly_value = ft.Text(

            "₹0.00", size=28, weight=ft.FontWeight.BOLD

        )

        budget_value = ft.Text(

            "₹0.00", size=28, weight=ft.FontWeight.BOLD

        )

        remaining_value = ft.Text(

            "₹0.00", size=28, weight=ft.FontWeight.BOLD

        )

        count_value = ft.Text(

            "0", size=28, weight=ft.FontWeight.BOLD

        )

        yearly_value = ft.Text(

            "₹0.00", size=28, weight=ft.FontWeight.BOLD

        )

        yearly_remaining_value = ft.Text(

            "₹0.00", size=28, weight=ft.FontWeight.BOLD

        )

        # Yearly budget progress and warning status.
        yearly_progress_text = ft.Text(
            "₹0.00 spent of ₹0.00",
            size=14,
        )
        yearly_progress = ft.ProgressBar(
            value=0,
            height=8,
        )
        yearly_status = ft.Text(
            "No yearly budget set",
            size=13,
        )



        analytics_total = ft.Text(

            "₹0.00", size=22, weight=ft.FontWeight.BOLD

        )

        analytics_average = ft.Text(

            "₹0.00", size=22, weight=ft.FontWeight.BOLD

        )

        analytics_highest = ft.Text(

            "₹0.00", size=22, weight=ft.FontWeight.BOLD

        )

        analytics_category = ft.Text(

            "No data", size=18, weight=ft.FontWeight.BOLD

        )
        dashboard_category = ft.Text(
            "No data", size=18, weight=ft.FontWeight.BOLD
)




        # =====================================================

        # MONTHLY BUDGET PROGRESS

        # =====================================================



        budget_progress_text = ft.Text(

            "₹0.00 spent of ₹0.00",

            size=14,

        )



        budget_progress = ft.ProgressBar(

            value=0,

            height=8,

        )



        budget_status = ft.Text(

            "No budget set",

            size=13,

        )



        category_chart = ft.Column(

            spacing=10,

        )

        # SVG-based donut chart for Flet 1.0.3 compatibility.
        donut_chart = ft.Image(
            src="data:image/svg+xml;base64," + base64.b64encode(
                b'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" viewBox="0 0 220 220"><circle cx="110" cy="110" r="76" fill="none" stroke="#9CA3AF" stroke-width="28"/></svg>'
            ).decode("ascii"),
            width=220,
            height=220,
        )

        donut_legend = ft.Column(
            spacing=8,
        )



        daily_chart = ft.Row(

            spacing=10,

            scroll=ft.ScrollMode.AUTO,

        )



        analytics_chart_message = ft.Text(

            "Charts update automatically when expenses change.",

            size=12,

        )



        # =====================================================

        # ADD EXPENSE CONTROLS

        # =====================================================



        expense_name = ft.TextField(

            label="Expense Name",

            hint_text="e.g. Coffee",

            expand=True,

        )



        expense_amount = ft.TextField(

            label="Amount",

            hint_text="e.g. 120",

            keyboard_type=ft.KeyboardType.NUMBER,

            expand=True,

        )



        expense_category = ft.Dropdown(

            label="Category",

            value="Food",

            options=[

                ft.DropdownOption(key=category, text=category)

                for category in CATEGORIES

            ],

            expand=True,

        )



        expense_date = ft.TextField(

            label="Date",

            value=today(),

            hint_text="YYYY-MM-DD",

            expand=True,

        )



        form_message = ft.Text("", size=14)



        add_expense_button = ft.Button(
            content="Add Expense",
            icon=ft.Icons.ADD,
            style=ft.ButtonStyle(
                bgcolor=COLOR_PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )



        # =====================================================

        # MONTHLY BUDGET CONTROLS

        # =====================================================



        budget_input = ft.TextField(

            label="Monthly Budget",

            hint_text="e.g. 5000",

            keyboard_type=ft.KeyboardType.NUMBER,

            expand=True,

        )



        budget_message = ft.Text("", size=14)



        save_budget_button = ft.Button(
            content="Save Budget",
            icon=ft.Icons.SAVE,
            style=ft.ButtonStyle(
                bgcolor=COLOR_PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )



        delete_budget_button = ft.Button(
            content="Delete Budget",
            icon=ft.Icons.DELETE_OUTLINE,
            style=ft.ButtonStyle(
                bgcolor=COLOR_DANGER,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )



        # =====================================================

        # YEARLY BUDGET CONTROLS

        # =====================================================



        yearly_budget_input = ft.TextField(

            label=f"Yearly Budget ({current_year()})",

            hint_text="e.g. 60000",

            keyboard_type=ft.KeyboardType.NUMBER,

            expand=True,

        )



        yearly_budget_message = ft.Text("", size=14)



        save_yearly_budget_button = ft.Button(
            content="Save Yearly Budget",
            icon=ft.Icons.SAVE,
            style=ft.ButtonStyle(
                bgcolor=COLOR_PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )



        delete_yearly_budget_button = ft.Button(
            content="Delete Yearly Budget",
            icon=ft.Icons.DELETE_OUTLINE,
            style=ft.ButtonStyle(
                bgcolor=COLOR_DANGER,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )



        # =====================================================

        # EXPENSE LIST CONTROLS

        # =====================================================



        search_field = ft.TextField(

            label="Search expenses",

            hint_text="Search by name or category",

            prefix_icon=ft.Icons.SEARCH,

            expand=True,

        )



        refresh_button = ft.Button(

            content="Refresh",

            icon=ft.Icons.REFRESH,

        )



        logout_button = ft.Button(

            content="Logout",

            icon=ft.Icons.LOGOUT,

        )



        expense_list = ft.Column(

            spacing=10,

        )



        expense_count_text = ft.Text(

            "0 expenses",

            size=14,

        )



        # =====================================================

        # HELPER FUNCTIONS FOR DASHBOARD

        # =====================================================



        def stat_card(title, value_control, subtitle=""):

            return ft.Card(

                content=ft.Container(

                    padding=18,

                    content=ft.Column(

                        [

                            ft.Text(

                                title,

                                size=14,

                                weight=ft.FontWeight.BOLD,

                            ),

                            value_control,

                            ft.Text(

                                subtitle,

                                size=12,

                            ),

                        ],

                        spacing=8,

                    ),

                ),

            )



        async def get_yearly_budget():

            key = f"{YEARLY_BUDGET_KEY_PREFIX}{current_year()}"

            value = await prefs.get(key)



            if value is None:

                return 0.0



            try:

                return float(value)

            except (ValueError, TypeError):

                return 0.0



        async def save_yearly_budget_value(amount):

            key = f"{YEARLY_BUDGET_KEY_PREFIX}{current_year()}"

            await prefs.set(key, str(amount))



        async def delete_yearly_budget_value():

            key = f"{YEARLY_BUDGET_KEY_PREFIX}{current_year()}"

            await prefs.remove(key)



        # =====================================================

        # LOAD MONTHLY BUDGET

        # =====================================================



        async def load_monthly_budget(monthly_total=None):

            if monthly_total is None:

                monthly_total = 0.0



            try:

                response = await api_request(

                    "GET",

                    f"/budget/{current_month()}",

                )



                if response.status_code == 200:

                    data = response.json()

                    budget = float(data.get("amount", 0) or 0)

                    budget_value.value = money(budget)



                    remaining = budget - monthly_total

                    # Keep the dashboard balance readable when spending exceeds the budget.
                    if remaining >= 0:
                        remaining_value.value = money(remaining)
                    else:
                        remaining_value.value = f"{money(abs(remaining))} over"

                    if budget > 0:
                        progress = monthly_total / budget
                        budget_progress.value = min(max(progress, 0), 1)

                        if progress >= 1:
                            budget_progress.color = COLOR_DANGER
                            over = monthly_total - budget
                            budget_status.value = (
                                f"🚨 Budget exceeded • {progress * 100:.0f}% used • "
                                f"{money(over)} over budget"
                            )
                            budget_status.color = COLOR_DANGER
                        elif progress >= 0.75:
                            budget_progress.color = COLOR_WARNING
                            budget_status.value = (
                                f"⚠️ Budget warning • {progress * 100:.0f}% used • "
                                f"{money(remaining)} remaining"
                            )
                            budget_status.color = COLOR_WARNING
                        else:
                            budget_progress.color = COLOR_SUCCESS
                            budget_status.value = (
                                f"{progress * 100:.0f}% used • "
                                f"{money(remaining)} remaining"
                            )
                            budget_status.color = None
                    else:
                        budget_progress.value = 0
                        budget_progress.color = COLOR_PRIMARY
                        budget_status.value = "No budget set"
                        budget_status.color = None



                    budget_progress_text.value = (

                        f"{money(monthly_total)} spent of "

                        f"{money(budget)}"

                    )



                    budget_input.value = str(int(budget)) if budget else ""



                    return budget



                if response.status_code == 404:

                    budget_value.value = money(0)

                    remaining_value.value = money(-monthly_total)

                    budget_progress.value = 0
                    budget_progress.color = COLOR_PRIMARY

                    budget_progress_text.value = (

                        f"{money(monthly_total)} spent of ₹0.00"

                    )

                    budget_status.value = "No budget set"
                    budget_status.color = None

                    budget_input.value = ""

                    return 0.0



                if response.status_code == 401:

                    await handle_unauthorized()

                    return 0.0



                budget_status.value = "Could not load budget."



            except requests.exceptions.ConnectionError:

                budget_status.value = "Backend unavailable."

            except requests.exceptions.Timeout:

                budget_status.value = "Budget request timed out."

            except Exception as error:

                budget_status.value = "Could not load budget."

                print("Budget load error:", error)



            return 0.0



        # =====================================================

        # UPDATE DASHBOARD

        # =====================================================



        async def update_dashboard():

            total = 0.0

            monthly = 0.0

            count = len(all_expenses)

            month = current_month()



            for expense in all_expenses:

                try:

                    amount = float(expense.get("amount", 0) or 0)

                except (ValueError, TypeError):

                    amount = 0.0



                total += amount



                if str(expense.get("date", ""))[:7] == month:

                    monthly += amount



            total_value.value = money(total)

            monthly_value.value = money(monthly)

            count_value.value = str(count)

            expense_count_text.value = (

                f"{count} expense" if count == 1 else f"{count} expenses"

            )



            budget = await load_monthly_budget(monthly)



            remaining_value.value = money(budget - monthly)



            yearly_total = 0.0

            year = str(current_year())



            for expense in all_expenses:

                if str(expense.get("date", "")).startswith(year):

                    try:

                        yearly_total += float(

                            expense.get("amount", 0) or 0

                        )

                    except (ValueError, TypeError):

                        pass



            yearly_value.value = money(yearly_total)

            yearly_budget = await get_yearly_budget()
            yearly_remaining = yearly_budget - yearly_total

            if yearly_budget > 0:
                yearly_ratio = yearly_total / yearly_budget
                yearly_progress.value = min(max(yearly_ratio, 0), 1)
                yearly_progress_text.value = (
                    f"{money(yearly_total)} spent of {money(yearly_budget)}"
                )

                if yearly_ratio >= 1:
                    yearly_progress.color = COLOR_DANGER
                    yearly_status.value = (
                        f"🚨 Yearly budget exceeded • {yearly_ratio * 100:.0f}% used • "
                        f"{money(abs(yearly_remaining))} over budget"
                    )
                    yearly_status.color = COLOR_DANGER
                    yearly_remaining_value.value = f"{money(abs(yearly_remaining))} over"
                elif yearly_ratio >= 0.8:
                    yearly_progress.color = COLOR_WARNING
                    yearly_status.value = (
                        f"⚠️ Yearly budget warning • {yearly_ratio * 100:.0f}% used • "
                        f"{money(yearly_remaining)} remaining"
                    )
                    yearly_status.color = COLOR_WARNING
                    yearly_remaining_value.value = money(yearly_remaining)
                else:
                    yearly_progress.color = COLOR_SUCCESS
                    yearly_status.value = (
                        f"{yearly_ratio * 100:.0f}% used • "
                        f"{money(yearly_remaining)} remaining"
                    )
                    yearly_status.color = None
                    yearly_remaining_value.value = money(yearly_remaining)
            else:
                yearly_progress.value = 0
                yearly_progress.color = COLOR_PRIMARY
                yearly_progress_text.value = (
                    f"{money(yearly_total)} spent of ₹0.00"
                )
                yearly_status.value = "Set a yearly budget to track progress."
                yearly_status.color = None
                yearly_remaining_value.value = money(0)

            page.update()



        # =====================================================

        # ANALYTICS

        # =====================================================



        async def load_analytics():

            total = 0.0

            highest = 0.0

            category_totals = {}



            for expense in all_expenses:

                try:

                    amount = float(expense.get("amount", 0) or 0)

                except (ValueError, TypeError):

                    amount = 0.0



                total += amount

                highest = max(highest, amount)



                category = expense.get("category") or "Misc"

                category_totals[category] = (

                    category_totals.get(category, 0.0) + amount

                )



            analytics_total.value = money(total)



            if all_expenses:

                analytics_average.value = money(

                    total / len(all_expenses)

                )

            else:

                analytics_average.value = money(0)



            analytics_highest.value = money(highest)



            if category_totals:

                top_category = max(

                    category_totals,

                    key=category_totals.get,

                )

                analytics_category.value = (

                    f"{top_category} ({money(category_totals[top_category])})"

                )
                analytics_category.update()

                dashboard_category.value = (
                    f"{top_category} ({money(category_totals[top_category])})"
                )
                dashboard_category.update()

            else:

                analytics_category.value = "No data"
                analytics_category.update()
                dashboard_category.value = "No data"
                dashboard_category.update()



            update_analytics_charts()

            page.update()



        # =====================================================

        # ANALYTICS CHARTS

        # =====================================================



        def update_analytics_charts():

            category_chart.controls.clear()

            daily_chart.controls.clear()



            if not all_expenses:

                category_chart.controls.append(

                    ft.Text("No category spending data yet.")

                )

                donut_legend.controls.clear()
                donut_legend.controls.append(
                    ft.Text("Add expenses to see category breakdown.")
                )
                donut_chart.src = "data:image/svg+xml;base64," + base64.b64encode(
                    b'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" viewBox="0 0 220 220"><circle cx="110" cy="110" r="76" fill="none" stroke="#9CA3AF" stroke-width="28"/></svg>'
                ).decode("ascii")



                daily_chart.controls.append(

                    ft.Container(

                        content=ft.Text("No recent spending data yet."),

                        padding=15,

                    )

                )



                analytics_chart_message.value = (

                    "Add an expense to see your spending charts."

                )

                return



            # -------------------------------------------------

            # CATEGORY CHART

            # -------------------------------------------------



            category_totals = {}



            for expense in all_expenses:

                category = expense.get("category") or "Misc"



                try:

                    amount = float(

                        expense.get("amount", 0) or 0

                    )

                except (ValueError, TypeError):

                    amount = 0.0



                category_totals[category] = (

                    category_totals.get(category, 0.0) + amount

                )



            sorted_categories = sorted(

                category_totals.items(),

                key=lambda item: item[1],

                reverse=True,

            )



            # Build an SVG donut from category totals. This avoids
            # ft.PieChart, which is unavailable in the installed Flet version.
            chart_categories = sorted_categories[:6]
            if len(sorted_categories) > 6:
                chart_categories.append(
                    (
                        "Other",
                        sum(amount for _, amount in sorted_categories[6:]),
                    )
                )

            chart_colors = list(CATEGORY_COLORS.values()) + ["#9CA3AF"]
            chart_total = sum(max(0, amount) for _, amount in chart_categories)
            circumference = 2 * math.pi * 76
            svg_parts = [
                '<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" viewBox="0 0 220 220">',
                '<circle cx="110" cy="110" r="76" fill="none" stroke="#9CA3AF" stroke-opacity="0.22" stroke-width="28"/>',
            ]
            donut_legend.controls.clear()
            dash_offset = 0.0

            for index, (category_name, category_amount) in enumerate(chart_categories):
                if category_amount <= 0 or chart_total <= 0:
                    continue

                fraction = category_amount / chart_total
                segment_length = circumference * fraction
                color = chart_colors[index % len(chart_colors)]
                svg_parts.append(
                    f'<circle cx="110" cy="110" r="76" fill="none" stroke="{color}" stroke-width="28" '
                    f'stroke-dasharray="{segment_length:.3f} {circumference - segment_length:.3f}" '
                    f'stroke-dashoffset="{-dash_offset:.3f}" transform="rotate(-90 110 110)"/>'
                )
                dash_offset += segment_length
                donut_legend.controls.append(
                    ft.Row(
                        [
                            ft.Container(
                                width=10,
                                height=10,
                                bgcolor=color,
                                border_radius=3,
                            ),
                            ft.Text(category_name, size=12, expand=True),
                            ft.Text(f"{fraction * 100:.0f}%", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text(money(category_amount), size=12),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

            svg_parts.append(
                '<circle cx="110" cy="110" r="55" fill="#FFFFFF" fill-opacity="0.96"/>'
            )
            svg_parts.append(
                f'<text x="110" y="105" text-anchor="middle" font-size="17" font-weight="600" fill="#111827">{chart_total:,.0f}</text>'
            )
            svg_parts.append(
                '<text x="110" y="125" text-anchor="middle" font-size="10" fill="#4B5563">Total spending</text></svg>'
            )
            donut_chart.src = "data:image/svg+xml;base64," + base64.b64encode(
                "".join(svg_parts).encode("utf-8")
            ).decode("ascii")

            top_categories = sorted_categories[:6]



            max_category_amount = max(

                (amount for _, amount in top_categories),

                default=0,

            )



            for category, amount in top_categories:

                ratio = (

                    amount / max_category_amount

                    if max_category_amount > 0

                    else 0

                )



                bar = ft.Container(

                    height=18,

                    bgcolor=CATEGORY_COLORS.get(category, "#9CA3AF"),

                    border_radius=8,

                    width=max(20, 300 * ratio),

                )



                category_chart.controls.append(

                    ft.Column(

                        [

                            ft.Row(

                                [

                                    ft.Text(

                                        category,

                                        width=110,

                                        size=13,

                                    ),

                                    ft.Container(

                                        content=bar,

                                        expand=True,

                                    ),

                                    ft.Text(

                                        money(amount),

                                        width=90,

                                        size=13,

                                        text_align=ft.TextAlign.RIGHT,

                                    ),

                                ],

                                vertical_alignment=ft.CrossAxisAlignment.CENTER,

                            ),

                        ],

                    )

                )



            # -------------------------------------------------

            # DAILY CHART

            # -------------------------------------------------



            daily_totals = {}



            for expense in all_expenses:

                date_value = str(

                    expense.get("date", "")

                )[:10]



                if not date_value:

                    continue



                try:

                    amount = float(

                        expense.get("amount", 0) or 0

                    )

                except (ValueError, TypeError):

                    amount = 0.0



                daily_totals[date_value] = (

                    daily_totals.get(date_value, 0.0) + amount

                )



            sorted_days = sorted(

                daily_totals.items(),

                key=lambda item: item[0],

                reverse=True,

            )[:7]



            sorted_days.reverse()



            max_daily_amount = max(

                (amount for _, amount in sorted_days),

                default=0,

            )



            for date_value, amount in sorted_days:

                ratio = (

                    amount / max_daily_amount

                    if max_daily_amount > 0

                    else 0

                )



                bar_height = max(20, int(120 * ratio))



                daily_chart.controls.append(

                    ft.Container(

                        width=75,

                        content=ft.Column(

                            [

                                ft.Container(

                                    height=130 - bar_height,

                                ),

                                ft.Container(

                                    width=35,

                                    height=bar_height,

                                    bgcolor=COLOR_DAILY_SPENDING,

                                    border_radius=6,

                                ),

                                ft.Text(

                                    date_value[5:],

                                    size=11,

                                    text_align=ft.TextAlign.CENTER,

                                ),

                                ft.Text(

                                    money(amount),

                                    size=10,

                                    text_align=ft.TextAlign.CENTER,

                                ),

                            ],

                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,

                            spacing=4,

                        ),

                    )

                )



            analytics_chart_message.value = (

                "Category chart shows your top spending categories. "

                "Recent spending shows the latest spending days."

            )



        # =====================================================

        # EXPENSE TILE

        # =====================================================



        def expense_tile(expense):

            expense_id = expense.get("id")

            name = expense.get("name", "Unnamed")

            amount = expense.get("amount", 0)

            category = expense.get("category", "Misc")

            date_value = expense.get("date", "")



            return ft.Card(

                content=ft.Container(

                    padding=15,

                    content=ft.Row(

                        [

                            ft.Column(

                                [

                                    ft.Text(

                                        name,

                                        size=17,

                                        weight=ft.FontWeight.BOLD,

                                    ),

                                    ft.Text(

                                        f"{category} • {date_value}",

                                        size=12,

                                    ),

                                ],

                                expand=True,

                            ),

                            ft.Text(

                                money(amount),

                                size=16,

                                weight=ft.FontWeight.BOLD,

                            ),

                            ft.IconButton(

                                icon=ft.Icons.EDIT,

                                tooltip="Edit Expense",

                                on_click=lambda e, item=expense:

                                    asyncio.create_task(

                                        open_edit_dialog(item)

                                    ),

                            ),

                            ft.IconButton(

                                icon=ft.Icons.DELETE_OUTLINE,

                                tooltip="Delete Expense",

                                on_click=lambda e, item=expense:

                                    asyncio.create_task(

                                        confirm_delete(item)

                                    ),

                            ),

                        ],

                        vertical_alignment=ft.CrossAxisAlignment.CENTER,

                    ),

                ),

            )



        # =====================================================

        # UPDATE EXPENSE LIST

        # =====================================================



        def update_expense_list():

            search_text = (

                (search_field.value or "").strip().lower()

            )



            filtered = []



            for expense in all_expenses:

                if not search_text:

                    filtered.append(expense)

                    continue



                name = str(

                    expense.get("name", "")

                ).lower()



                category = str(

                    expense.get("category", "")

                ).lower()



                if (

                    search_text in name

                    or search_text in category

                ):

                    filtered.append(expense)



            expense_list.controls.clear()



            if not filtered:

                expense_list.controls.append(

                    ft.Container(

                        padding=20,

                        content=ft.Text(

                            "No expenses found.",

                            text_align=ft.TextAlign.CENTER,

                        ),

                    )

                )

            else:

                for expense in filtered:

                    expense_list.controls.append(

                        expense_tile(expense)

                    )



            expense_count_text.value = (

                f"{len(filtered)} result"

                if len(filtered) == 1

                else f"{len(filtered)} results"

            )



            page.update()



        # =====================================================

        # REFRESH ALL

        # =====================================================



        async def refresh_all():

            await load_expenses()

            await update_dashboard()

            await load_analytics()

            update_expense_list()

            update_analytics_charts()

            page.update()



        # =====================================================

        # LOAD EXPENSES

        # =====================================================



        async def load_expenses():

            nonlocal all_expenses



            status.value = "Backend: Loading..."

            page.update()



            try:

                response = await api_request(

                    "GET",

                    "/expenses",

                )



                if response.status_code == 200:

                    data = response.json()



                    if isinstance(data, list):

                        all_expenses = data

                    elif isinstance(data, dict):

                        all_expenses = data.get(

                            "expenses",

                            data.get("data", []),

                        )

                    else:

                        all_expenses = []



                    status.value = "Backend: Connected ✅"



                    return



                if response.status_code == 401:

                    await handle_unauthorized()

                    return



                status.value = (

                    f"Backend: Error {response.status_code} ❌"

                )



            except requests.exceptions.ConnectionError:

                status.value = "Backend: Offline ❌"



            except requests.exceptions.Timeout:

                status.value = "Backend: Timeout ❌"



            except Exception as error:

                status.value = "Backend: Error ❌"

                print("Load expenses error:", error)



        # =====================================================

        # ADD EXPENSE

        # =====================================================



        async def add_expense(e):

            name = (expense_name.value or "").strip()

            amount = parse_positive_amount(

                expense_amount.value

            )

            category = expense_category.value

            date_value = (

                expense_date.value or ""

            ).strip()



            form_message.value = ""



            if not name:

                form_message.value = (

                    "Give this expense a name first."

                )

                page.update()

                return



            if len(name) > 120:

                form_message.value = (

                    "Expense name is too long."

                )

                page.update()

                return



            if amount is None:

                form_message.value = (

                    "Enter an amount greater than ₹0."

                )

                page.update()

                return



            if category not in CATEGORIES:

                form_message.value = (

                    "Please choose a valid category."

                )

                page.update()

                return



            if not valid_date(date_value):

                form_message.value = (

                    "Use date format YYYY-MM-DD."

                )

                page.update()

                return



            add_expense_button.disabled = True
            add_expense_button.content = "Adding to your tracker..."
            add_expense_button.icon = ft.Icons.HOURGLASS_TOP

            form_message.value = (
                "Adding this expense to your tracker..."
            )


            page.update()



            try:

                response = await api_request(

                    "POST",

                    "/expenses",

                    json={

                        "name": name,

                        "amount": amount,

                        "category": category,

                        "date": date_value,

                    },

                )



                if response.status_code in (200, 201):

                    expense_name.value = ""

                    expense_amount.value = ""

                    expense_category.value = "Food"

                    expense_date.value = today()



                    show_message(
                        f'Expense added ✓  •  {name} • ₹{amount:.2f}'
                    )

                    form_message.value = (
                        "Your expense is now part of your tracker."
                    )





                    await load_expenses()

                    await update_dashboard()

                    await load_analytics()

                    update_expense_list()

                    update_analytics_charts()

                    page.update()

                    add_expense_button.disabled = False
                    add_expense_button.content = "Add Expense"
                    add_expense_button.icon = ft.Icons.ADD

                    page.update()

                    return



                if response.status_code == 401:

                    await handle_unauthorized()

                    return



                form_message.value = response_detail(

                    response,

                    "Could not add this expense.",

                )



            except requests.exceptions.ConnectionError:

                form_message.value = (

                    "Could not connect to backend ❌"

                )

            except requests.exceptions.Timeout:

                form_message.value = (

                    "Adding expense timed out ❌"

                )

            except Exception as error:

                form_message.value = (

                    "Something went wrong while adding the expense ❌"

                )

                print("Add expense error:", error)



            add_expense_button.disabled = False
            add_expense_button.content = "Add Expense"
            add_expense_button.icon = ft.Icons.ADD


            page.update()




        add_expense_button.on_click = add_expense



        # =====================================================
        # EDIT EXPENSE
        # =====================================================

        async def open_edit_dialog(expense):

            expense_id = expense.get("id")

            if expense_id is None:
                show_message("Invalid expense ID ❌")
                return

            edit_name = ft.TextField(
                label="Expense Name",
                value=str(expense.get("name", "")),
            )

            edit_amount = ft.TextField(
                label="Amount",
                value=str(expense.get("amount", "")),
                keyboard_type=ft.KeyboardType.NUMBER,
            )

            edit_category = ft.Dropdown(
                label="Category",
                value=expense.get("category", "Misc"),
                options=[
                    ft.DropdownOption(
                        key=category,
                        text=category,
                    )
                    for category in CATEGORIES
                ],
            )

            edit_date = ft.TextField(
                label="Date",
                value=str(
                    expense.get(
                        "date",
                        today(),
                    )
                ),
                hint_text="YYYY-MM-DD",
            )

            edit_message = ft.Text("")

            save_button = ft.Button(
                content="Save Changes",
                icon=ft.Icons.SAVE,
            )

            async def save_edit(e):

                name = (
                    edit_name.value or ""
                ).strip()

                amount = parse_positive_amount(
                    edit_amount.value or ""
                )

                category = (
                    edit_category.value or "Misc"
                )

                date_value = (
                    edit_date.value or ""
                ).strip()

                edit_message.value = ""

                if not name:
                    edit_message.value = (
                        "Name cannot be empty."
                    )
                    page.update()
                    return

                if len(name) > 120:
                    edit_message.value = (
                        "Expense name is too long."
                    )
                    page.update()
                    return

                if amount is None:
                    edit_message.value = (
                        "Enter a valid amount greater than 0."
                    )
                    page.update()
                    return

                if category not in CATEGORIES:
                    edit_message.value = (
                        "Select a valid category."
                    )
                    page.update()
                    return

                if not valid_date(date_value):
                    edit_message.value = (
                        "Date must be YYYY-MM-DD."
                    )
                    page.update()
                    return

                payload = {
                    "name": name,
                    "amount": amount,
                    "category": category,
                    "date": date_value,
                }

                save_button.disabled = True
                save_button.content = "Updating expense..."
                save_button.icon = ft.Icons.HOURGLASS_TOP

                edit_message.value = (
                    "Saving your changes..."
                )

                page.update()

                try:

                    response = await api_request(
                        "PUT",
                        f"/expenses/{expense_id}",
                        json=payload,
                    )

                    # Compatibility fallback
                    # for APIs exposing PATCH only.
                    if response.status_code == 405:
                        response = await api_request(
                            "PATCH",
                            f"/expenses/{expense_id}",
                            json=payload,
                        )

                    if response.status_code in (
                        200,
                        201,
                    ):

                        page.pop_dialog()

                        await refresh_all()

                        show_message(
                            f'Expense updated ✓  •  {name} • ₹{amount:.2f}'
                        )

                        return

                    if response.status_code == 401:

                        page.pop_dialog()

                        await handle_unauthorized()

                        return

                    edit_message.value = (
                        response_detail(
                            response,
                            "Could not update expense.",
                        )
                        + " ❌"
                    )

                except requests.exceptions.ConnectionError:

                    edit_message.value = (
                        "Could not connect to backend ❌"
                    )

                except requests.exceptions.Timeout:

                    edit_message.value = (
                        "Update request timed out ❌"
                    )

                except Exception as error:

                    edit_message.value = (
                        "Something went wrong while updating ❌"
                    )

                    print(
                        "Update error:",
                        error,
                    )

                save_button.disabled = False
                save_button.content = "Save Changes"
                save_button.icon = ft.Icons.SAVE

                page.update()

            save_button.on_click = save_edit

            dialog = ft.AlertDialog(
                modal=True,

                title=ft.Text(
                    "Edit Expense"
                ),

                content=ft.Column(
                    [
                        edit_name,
                        edit_amount,
                        edit_category,
                        edit_date,
                        edit_message,
                    ],

                    tight=True,

                    spacing=12,
                ),

                actions=[
                    ft.TextButton(
                        "Keep Expense",
                        on_click=lambda e:
                            page.pop_dialog(),
                    ),

                    save_button,
                ],
            )

            page.show_dialog(dialog)



        # =====================================================
        # DELETE + 5 SECOND UNDO
        # =====================================================

        async def confirm_delete(expense):

            expense_id = expense.get("id")

            name = str(
                expense.get(
                    "name",
                    "this expense",
                )
            )

            amount = expense.get(
                "amount",
                0,
            )

            if expense_id is None:

                show_message(
                    "Invalid expense ID ❌"
                )

                return

            # -------------------------------------------------
            # CONFIRM DELETE ACTION
            # -------------------------------------------------

            async def delete_confirmed(e):

                delete_button.disabled = True

                delete_button.content = (
                    "Deleting..."
                )

                delete_button.icon = (
                    ft.Icons.HOURGLASS_TOP
                )

                page.update()

                page.pop_dialog()

                try:

                    response = await api_request(
                        "DELETE",
                        f"/expenses/{expense_id}",
                    )

                    # -------------------------------------------------
                    # DELETE SUCCESS
                    # -------------------------------------------------

                    if response.status_code in (
                        200,
                        204,
                    ):

                        deleted_expense = dict(
                            expense
                        )

                        deleted_at = (
                            asyncio
                            .get_running_loop()
                            .time()
                        )

                        undo_used = False

                        # Refresh dashboard immediately
                        await load_expenses()

                        await update_dashboard()

                        await load_analytics()

                        update_expense_list()

                        update_analytics_charts()

                        # -------------------------------------------------
                        # UNDO EXPENSE
                        # -------------------------------------------------

                        async def undo_expense(e):

                            nonlocal undo_used

                            if undo_used:
                                return

                            elapsed = (
                                asyncio
                                .get_running_loop()
                                .time()
                                - deleted_at
                            )

                            if (
                                elapsed
                                > UNDO_DURATION_SECONDS
                            ):

                                show_message(
                                    "Undo window expired."
                                )

                                return

                            undo_used = True

                            restore_payload = {
                                "name": (
                                    deleted_expense.get(
                                        "name",
                                        "",
                                    )
                                ),

                                "amount": (
                                    deleted_expense.get(
                                        "amount",
                                        0,
                                    )
                                ),

                                "category": (
                                    deleted_expense.get(
                                        "category",
                                        "Misc",
                                    )
                                ),

                                "date": (
                                    deleted_expense.get(
                                        "date",
                                        today(),
                                    )
                                ),
                            }

                            try:

                                restore_response = (
                                    await api_request(
                                        "POST",
                                        "/expenses/",
                                        json=restore_payload,
                                    )
                                )

                                if (
                                    restore_response
                                    .status_code
                                    in (
                                        200,
                                        201,
                                    )
                                ):

                                    await refresh_all()

                                    show_message(
                                        "Expense restored successfully ✅"
                                    )

                                elif (
                                    restore_response
                                    .status_code
                                    == 401
                                ):

                                    await handle_unauthorized()

                                else:

                                    show_message(
                                        response_detail(
                                            restore_response,
                                            "Could not restore expense.",
                                        )
                                    )

                            except requests.exceptions.ConnectionError:

                                show_message(
                                    "Could not connect to backend ❌"
                                )

                            except requests.exceptions.Timeout:

                                show_message(
                                    "Restore request timed out ❌"
                                )

                            except Exception as error:

                                print(
                                    "Undo error:",
                                    error,
                                )

                                show_message(
                                    "Could not restore expense ❌"
                                )

                        # -------------------------------------------------
                        # DELETE SUCCESS SNACKBAR
                        # -------------------------------------------------

                        snackbar = ft.SnackBar(

                            content=ft.Text(
                                f"Expense removed ✓  •  "
                                f"{name} • "
                                f"{money(amount)}"
                            ),

                            action=ft.SnackBarAction(
                                label="UNDO",
                                on_click=undo_expense,
                            ),

                            duration=UNDO_DURATION_MS,
                        )

                        page.show_dialog(
                            snackbar
                        )

                        return

                    # -------------------------------------------------
                    # SESSION EXPIRED
                    # -------------------------------------------------

                    if response.status_code == 401:

                        await handle_unauthorized()

                        return

                    # -------------------------------------------------
                    # OTHER BACKEND ERRORS
                    # -------------------------------------------------

                    show_message(
                        response_detail(
                            response,
                            "Could not delete expense.",
                        )
                    )

                except requests.exceptions.ConnectionError:

                    show_message(
                        "Could not connect to backend ❌"
                    )

                except requests.exceptions.Timeout:

                    show_message(
                        "Delete request timed out ❌"
                    )

                except Exception as error:

                    print(
                        "Delete error:",
                        error,
                    )

                    show_message(
                        "Could not delete expense ❌"
                    )

                finally:

                    delete_button.disabled = False

                    delete_button.content = (
                        "Delete Expense"
                    )

                    delete_button.icon = (
                        ft.Icons.DELETE
                    )

                    page.update()

            # -------------------------------------------------
            # DELETE BUTTON
            # -------------------------------------------------

            delete_button = ft.Button(
                content="Delete Expense",
                icon=ft.Icons.DELETE,
                on_click=delete_confirmed,
                style=ft.ButtonStyle(
                    bgcolor=COLOR_DANGER,
                    color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
            )

            # -------------------------------------------------
            # CONFIRMATION DIALOG
            # -------------------------------------------------

            dialog = ft.AlertDialog(

                modal=True,

                title=ft.Text(
                    "Delete Expense?"
                ),

                content=ft.Text(
                    f'Are you sure you want to delete "{name}"?\n'
                    "You can undo this deletion for 5 seconds."
                ),

                actions=[

                    ft.TextButton(
                        "Keep Expense",
                        on_click=lambda e:
                            page.pop_dialog(),
                    ),

                    delete_button,

                ],
            )

            page.show_dialog(
                dialog
            )


        # =====================================================
        # MONTHLY BUDGET
        # =====================================================



        # =====================================================
        # MONTHLY BUDGET
        # =====================================================

        async def save_budget(e):

            budget_message.value = ""

            amount = parse_positive_amount(
                budget_input.value or ""
            )

            if amount is None:

                budget_message.value = (
                    "Enter a monthly budget greater than ₹0."
                )

                page.update()

                return

            save_budget_button.disabled = True

            budget_message.value = (
                "Saving your monthly budget..."
            )

            page.update()

            try:

                response = await api_request(
                    "POST",
                    "/budget/",
                    json={
                        "month": current_month(),
                        "amount": amount,
                    },
                )

                if response.status_code in (
                    200,
                    201,
                ):

                    budget_input.value = ""

                    budget_message.value = (
                        f"Monthly budget set to "
                        f"{money(amount)}. "
                        "You are ready to track it 🎯"
                    )

                    await update_dashboard()

                    return

                if response.status_code == 401:

                    await handle_unauthorized()

                    return

                budget_message.value = (
                    f"Budget update failed ❌ "
                    f"({response.status_code})"
                )

            except requests.exceptions.ConnectionError:

                budget_message.value = (
                    "Could not reach the backend ❌"
                )

            except requests.exceptions.Timeout:

                budget_message.value = (
                    "Budget request timed out ❌"
                )

            except Exception as error:

                budget_message.value = (
                    "Something went wrong while "
                    "saving the budget ❌"
                )

                print(
                    "Budget error:",
                    error,
                )

            finally:

                save_budget_button.disabled = False

                page.update()


        async def delete_budget(e):

            delete_budget_button.disabled = True

            budget_message.value = (
                "Removing this month's budget..."
            )

            page.update()

            try:

                response = await api_request(
                    "DELETE",
                    f"/budget/{current_month()}",
                )

                if response.status_code in (
                    200,
                    204,
                ):

                    budget_input.value = ""

                    budget_message.value = (
                        "Monthly budget removed. "
                        "Your expenses are still safe."
                    )

                    await update_dashboard()

                    return

                if response.status_code == 401:

                    await handle_unauthorized()

                    return

                if response.status_code == 404:

                    budget_message.value = (
                        "No monthly budget is set "
                        "for this month."
                    )

                else:

                    budget_message.value = (
                        f"Delete budget failed ❌ "
                        f"({response.status_code})"
                    )

            except requests.exceptions.ConnectionError:

                budget_message.value = (
                    "Could not reach the backend ❌"
                )

            except requests.exceptions.Timeout:

                budget_message.value = (
                    "Budget delete request timed out ❌"
                )

            except Exception as error:

                budget_message.value = (
                    "Something went wrong while "
                    "deleting the budget ❌"
                )

                print(
                    "Budget delete error:",
                    error,
                )

            finally:

                delete_budget_button.disabled = False

                page.update()


        # =====================================================
        # YEARLY BUDGET
        # =====================================================

        async def save_yearly_budget(e):

            yearly_budget_message.value = ""

            amount = parse_positive_amount(
                yearly_budget_input.value or ""
            )

            if amount is None:

                yearly_budget_message.value = (
                    "Enter a yearly budget greater than ₹0."
                )

                page.update()

                return

            save_yearly_budget_button.disabled = True

            yearly_budget_message.value = (
                "Saving yearly budget..."
            )

            page.update()

            try:

                await save_yearly_budget_value(
                    amount
                )

                yearly_budget_input.value = str(amount)

                yearly_budget_message.value = (
                    f"Yearly budget for "
                    f"{current_year()} is "
                    f"{money(amount)} 🎯"
                )

                await update_dashboard()

            except Exception as error:

                yearly_budget_message.value = (
                    "Could not save yearly budget ❌"
                )

                print(
                    "Yearly budget save error:",
                    error,
                )

            finally:

                save_yearly_budget_button.disabled = False

                page.update()


        async def delete_yearly_budget(e):

            delete_yearly_budget_button.disabled = True

            yearly_budget_message.value = (
                "Removing yearly budget..."
            )

            page.update()

            try:

                await delete_yearly_budget_value()

                yearly_budget_input.value = ""

                yearly_budget_message.value = (
                    f"Yearly budget for "
                    f"{current_year()} removed."
                )

                await update_dashboard()

            except Exception as error:

                yearly_budget_message.value = (
                    "Could not delete yearly budget ❌"
                )

                print(
                    "Yearly budget delete error:",
                    error,
                )

            finally:

                delete_yearly_budget_button.disabled = False

                page.update()


        # =====================================================
        # SEARCH / REFRESH / LOGOUT
        # =====================================================

        def search_changed(e):

            update_expense_list()

            page.update()


        search_field.on_change = search_changed


        async def refresh(e):

            status.value = "Refreshing..."

            page.update()

            await refresh_all()


        async def logout(e):

            nonlocal access_token
            nonlocal refresh_token
            nonlocal current_user

            # =================================================
            # CLEAR CURRENT SESSION
            # =================================================

            access_token = None
            refresh_token = None
            current_user = None

            # =================================================
            # CLEAR REMEMBERED SESSION
            # =================================================

            await prefs.remove(
                REMEMBER_TOKEN_KEY
            )

            await prefs.remove(
                REMEMBER_REFRESH_TOKEN_KEY
            )

            await prefs.remove(
                REMEMBER_EMAIL_KEY
            )

            # =================================================
            # RETURN TO LOGIN
            # =================================================

            await show_login(
                "Logged out successfully."
            )



        # =====================================================
        # CONNECT BUTTON EVENTS
        # =====================================================

        add_expense_button.on_click = add_expense

        save_budget_button.on_click = save_budget

        delete_budget_button.on_click = delete_budget

        save_yearly_budget_button.on_click = (
            save_yearly_budget
        )

        delete_yearly_budget_button.on_click = (
            delete_yearly_budget
        )

        refresh_button.on_click = refresh

        logout_button.on_click = logout


        # =====================================================
        # DASHBOARD UI
        # =====================================================

        header = ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            "Expense Tracker",
                            size=30,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Track your spending. Stay in control.",
                            size=14,
                        ),
                    ],
                    spacing=4,
                    expand=True,
                ),

                make_theme_button(),

                status,

                logout_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )


        # =====================================================
        # MAIN STAT CARDS
        # =====================================================

        stats_section = ft.ResponsiveRow(
            [
                ft.Container(
                    content=stat_card(
                        "Total Expense",
                        total_value,
                        "All recorded expenses",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=stat_card(
                        "This Month",
                        monthly_value,
                        "Current month spending",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=stat_card(
                        "Monthly Budget",
                        budget_value,
                        "Current month budget",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=stat_card(
                        "Remaining",
                        remaining_value,
                        "Monthly budget remaining",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),
            ],
            spacing=10,
            run_spacing=10,
        )


        # =====================================================
        # SECONDARY STAT CARDS
        # =====================================================

        secondary_stats = ft.ResponsiveRow(
            [
                ft.Container(
                    content=stat_card(
                        "Expense Count",
                        count_value,
                        "Total number of expenses",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=stat_card(
                        "Yearly Spending",
                        yearly_value,
                        f"Spending in {current_year()}",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=stat_card(
                        "Yearly Remaining",
                        yearly_remaining_value,
                        f"Based on {current_year()} budget",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=stat_card(
                        "Top Category",
                        dashboard_category,
                        "Highest spending category",
                    ),
                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),
            ],
            spacing=10,
            run_spacing=10,
        )


        # =====================================================
        # MONTHLY BUDGET PROGRESS CARD
        # =====================================================

        monthly_progress_card = ft.Card(
            content=ft.Container(
                padding=20,

                content=ft.Column(
                    [
                        ft.Text(
                            "Monthly Budget Progress",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                        ),

                        ft.Text(
                            "See how much of your monthly budget "
                            "you have already used.",
                            size=13,
                        ),

                        ft.Container(
                            height=8,
                        ),

                        budget_status,

                        budget_progress,

                        budget_progress_text,
                    ],

                    spacing=10,
                ),
            ),
        )


        # =====================================================
        # ANALYTICS SUMMARY
        # =====================================================

        analytics_summary = ft.ResponsiveRow(
            [
                ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            padding=18,

                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Total Spending",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    ),

                                    analytics_total,

                                    ft.Text(
                                        "Across all expenses",
                                        size=11,
                                    ),
                                ],

                                spacing=6,
                            ),
                        ),
                    ),

                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            padding=18,

                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Average Expense",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    ),

                                    analytics_average,

                                    ft.Text(
                                        "Average per expense",
                                        size=11,
                                    ),
                                ],

                                spacing=6,
                            ),
                        ),
                    ),

                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            padding=18,

                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Highest Expense",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    ),

                                    analytics_highest,

                                    ft.Text(
                                        "Largest single expense",
                                        size=11,
                                    ),
                                ],

                                spacing=6,
                            ),
                        ),
                    ),

                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),

                ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            padding=18,

                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Top Category",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    ),

                                    analytics_category,

                                    ft.Text(
                                        "Highest spending category",
                                        size=11,
                                    ),
                                ],

                                spacing=6,
                            ),
                        ),
                    ),

                    col={
                        "sm": 12,
                        "md": 6,
                        "lg": 3,
                    },
                ),
            ],

            spacing=10,
            run_spacing=10,
        )


        # =====================================================
        # CATEGORY SPENDING GRAPH
        # =====================================================

        category_chart_card = ft.Card(
            content=ft.Container(
                padding=20,

                content=ft.Column(
                    [
                        ft.Text(
                            "Spending by Category",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                        ),

                        ft.Text(
                            "Your top spending categories.",
                            size=13,
                        ),

                        ft.Container(
                            height=6,
                        ),

                        ft.Row(
                            [
                                ft.Container(
                                    content=donut_chart,
                                    width=220,
                                    height=220,
                                ),
                                ft.Container(
                                    content=donut_legend,
                                    expand=True,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                        ),

                        ft.Divider(),

                        ft.Text(
                            "Spending by Amount",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),

                        category_chart,
                    ],

                    spacing=8,
                ),
            ),
        )


        # =====================================================
        # RECENT SPENDING GRAPH
        # =====================================================

        daily_chart_card = ft.Card(
            content=ft.Container(
                padding=20,

                content=ft.Column(
                    [
                        ft.Text(
                            "Recent Spending",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                        ),

                        ft.Text(
                            "Daily spending for your latest "
                            "recorded days.",
                            size=13,
                        ),

                        ft.Container(
                            height=10,
                        ),

                        daily_chart,

                    ],

                    spacing=8,
                ),
            ),
        )


        analytics_graphs = ft.ResponsiveRow(
            [
                ft.Container(
                    content=category_chart_card,

                    col={
                        "sm": 12,
                        "md": 12,
                        "lg": 6,
                    },
                ),

                ft.Container(
                    content=daily_chart_card,

                    col={
                        "sm": 12,
                        "md": 12,
                        "lg": 6,
                    },
                ),
            ],

            spacing=10,
            run_spacing=10,
        )


        # =====================================================
        # ANALYTICS INFORMATION
        # =====================================================

        analytics_info_card = ft.Card(
            content=ft.Container(
                padding=15,

                content=analytics_chart_message,
            ),
        )


        # =====================================================
        # ADD EXPENSE CARD
        # =====================================================

        add_expense_card = ft.Card(
            content=ft.Container(
                padding=20,

                content=ft.Column(
                    [
                        ft.Text(
                            "Add Expense",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),

                        ft.Text(
                            "Record a new expense.",
                            size=13,
                        ),

                        ft.ResponsiveRow(
                            [
                                ft.Container(
                                    content=expense_name,
                                    col={
                                        "sm": 12,
                                        "md": 6,
                                        "lg": 6,
                                    },
                                ),

                                ft.Container(
                                    content=expense_amount,
                                    col={
                                        "sm": 12,
                                        "md": 6,
                                        "lg": 6,
                                    },
                                ),

                                ft.Container(
                                    content=expense_category,
                                    col={
                                        "sm": 12,
                                        "md": 6,
                                        "lg": 6,
                                    },
                                ),

                                ft.Container(
                                    content=expense_date,
                                    col={
                                        "sm": 12,
                                        "md": 6,
                                        "lg": 6,
                                    },
                                ),
                            ],

                            spacing=10,
                            run_spacing=10,
                        ),

                        form_message,

                        add_expense_button,
                    ],

                    spacing=12,
                ),
            ),
        )


        # =====================================================
        # MONTHLY BUDGET CARD
        # =====================================================

        monthly_budget_card = ft.Card(
            content=ft.Container(
                padding=20,

                content=ft.Column(
                    [
                        ft.Text(
                            "Monthly Budget",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),

                        ft.Text(
                            f"Set your budget for {current_month()}.",
                            size=13,
                        ),

                        ft.Row(
                            [
                                budget_input,
                            ],

                            expand=True,
                        ),

                        budget_message,

                        ft.Row(
                            [
                                save_budget_button,
                                delete_budget_button,
                            ],

                            wrap=True,
                            spacing=10,
                        ),
                    ],

                    spacing=12,
                ),
            ),
        )


        # =====================================================
        # YEARLY BUDGET CARD
        # =====================================================

        yearly_budget_card = ft.Card(
            content=ft.Container(
                padding=20,

                content=ft.Column(
                    [
                        ft.Text(
                            "Yearly Budget",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),

                        ft.Text(
                            f"Manage your {current_year()} "
                            "annual budget.",
                            size=13,
                        ),

                        yearly_progress_text,
                        yearly_progress,
                        yearly_status,

                        yearly_budget_input,

                        yearly_budget_message,

                        ft.Row(
                            [
                                save_yearly_budget_button,
                                delete_yearly_budget_button,
                            ],

                            wrap=True,
                            spacing=10,
                        ),
                    ],

                    spacing=12,
                ),
            ),
        )


        # =====================================================
        # BUDGET SECTION
        # =====================================================

        budget_section = ft.ResponsiveRow(
            [
                ft.Container(
                    content=monthly_budget_card,

                    col={
                        "sm": 12,
                        "md": 12,
                        "lg": 6,
                    },
                ),

                ft.Container(
                    content=yearly_budget_card,

                    col={
                        "sm": 12,
                        "md": 12,
                        "lg": 6,
                    },
                ),
            ],

            spacing=10,
            run_spacing=10,
        )


        # =====================================================
        # EXPENSE LIST CARD
        # =====================================================

        expense_list_card = ft.Card(
            content=ft.Container(
                padding=20,

                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            "All Expenses",
                                            size=22,
                                            weight=ft.FontWeight.BOLD,
                                        ),

                                        expense_count_text,
                                    ],

                                    spacing=3,
                                    expand=True,
                                ),

                                refresh_button,
                            ],

                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                        ),

                        search_field,

                        ft.Divider(),

                        expense_list,
                    ],

                    spacing=12,
                ),
            ),
        )


        # =====================================================
        # ADD EVERYTHING TO PAGE
        # =====================================================

        page.add(
            ft.Column(
                [
                    header,

                    ft.Container(
                        height=10,
                    ),

                    stats_section,

                    secondary_stats,

                    ft.Container(
                        height=5,
                    ),

                    monthly_progress_card,

                    ft.Container(
                        height=5,
                    ),

                    ft.Text(
                        "Analytics",
                        size=25,
                        weight=ft.FontWeight.BOLD,
                    ),

                    analytics_summary,

                    analytics_graphs,

                    analytics_info_card,

                    ft.Container(
                        height=5,
                    ),

                    add_expense_card,

                    budget_section,

                    expense_list_card,
                ],

                spacing=12,
            )
        )


        # =====================================================
        # INITIAL DASHBOARD LOAD
        # =====================================================

        await load_expenses()

        await update_dashboard()

        await load_analytics()

        update_expense_list()

        update_analytics_charts()

        page.update()


    # =========================================================
    # REMEMBERED SESSION
    # =========================================================

    async def restore_remembered_session():

        nonlocal access_token
        nonlocal refresh_token
        nonlocal current_user

        # =====================================================
        # LOAD SAVED SESSION
        # =====================================================

        remembered_token = await prefs.get(
            REMEMBER_TOKEN_KEY
        )

        remembered_refresh_token = await prefs.get(
            REMEMBER_REFRESH_TOKEN_KEY
        )

        remembered_email = await prefs.get(
            REMEMBER_EMAIL_KEY
        )

        # =====================================================
        # NO COMPLETE SAVED SESSION
        # =====================================================

        if (
            not remembered_token
            or not remembered_refresh_token
            or not remembered_email
        ):

            await show_login()

            return

        # =====================================================
        # RESTORE SESSION
        # =====================================================

        access_token = remembered_token
        refresh_token = remembered_refresh_token
        current_user = remembered_email

        try:

            response = await api_request(
                "GET",
                "/expenses",
            )

            # =================================================
            # SESSION VALID
            # =================================================

            if response.status_code == 200:

                await show_dashboard()

                return

            # =================================================
            # ACCESS + REFRESH TOKEN BOTH INVALID
            # =================================================

            if response.status_code in (
                401,
                403,
            ):

                await handle_unauthorized()

                return

            # =================================================
            # OTHER RESPONSE
            # =================================================

            await show_login()

        except requests.exceptions.ConnectionError:

            # Keep saved tokens.
            # Backend may simply be offline.

            await show_login(
                "Backend is offline. "
                "Please start FastAPI "
                "and try again."
            )

        except requests.exceptions.Timeout:

            await show_login(
                "Backend request timed out. "
                "Please try again."
            )

        except Exception as error:

            print(
                "Session restore error:",
                error,
            )

            await show_login()

    # Restore the previous session when Remember Me was enabled.
    # If no complete saved session exists, this opens the login screen.
    await restore_remembered_session()


if __name__ == "__main__":
    ft.run(main)
