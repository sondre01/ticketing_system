# TicketFlow - Ticketing System

TicketFlow is a modern, responsive ticketing system designed to streamline issue tracking, customer support, and developer workflows. This project exposes you to core Python backend services, relational database querying with raw PostgreSQL, and modern vanilla web designs on the frontend.

## 🚀 Technology Stack

- **Frontend**: Vanilla HTML5, Vanilla CSS3 (custom styling system with CSS variables), and ES6+ JavaScript.
- **Backend**: Python 3.13+, FastAPI (for rapid, type-safe REST API endpoints), and Uvicorn (ASGI server).
- **Database**: PostgreSQL (handling raw SQL queries without high-level ORMs for SQL training).
- **Security**: JWT (JSON Web Tokens) for stateless authentication and bcrypt for industry-standard password hashing.

---

## 🎨 Theme & Styling System

The application utilizes a dark theme with yellow accents, following the design principles below:

- **Editor & Sidebar Background (Deep Charcoal)**: `#1c1c1c`
- **Main Dashboard Body Background (Near Black)**: `#121212`
- **Header & Outer Panels (Pitch Black)**: `#0a0a0a`
- **Accent Details & Controls (Warm Yellow)**: `#facc15` (with hover effects scaling to `#eab308` and subtle `#facc15` shadows/glows).
- **Fonts**: `Outfit` (for modern, structural headings) and `Inter` (for readability in body text and logs).

---

## 📁 Project Directory Structure

```
ticketing_system/
├── backend/
│   ├── __init__.py
│   ├── auth.py          # Hashing (bcrypt) & Token (PyJWT) utility functions
│   ├── config.py        # Environment variables parser (.env loader)
│   ├── database.py      # Connection pool manager and SQL execution cursor
│   ├── main.py          # FastAPI application routes, middleware, and static mounting
│   └── requirements.txt # Python package declarations
├── frontend/
│   ├── css/
│   │   └── style.css    # Unified application stylesheet (auth and dashboard layouts)
│   ├── js/
│   │   └── app.js       # Form validation, API fetch client, and session controls
│   ├── dashboard.html   # Main post-auth customer/agent panel
│   └── index.html       # Sign-in and registration landing page
├── .env                 # Database credentials and secret keys (local gitignored file)
├── .env.example         # Template environment configuration file
├── index.html           # Root router redirecting local clicks to frontend/index.html
├── schema.sql           # Database schema containing users definition
└── README.md            # Project overview and instruction guide (this file)
```

---

## ✨ Features Implemented

### 1. Database Schema (`schema.sql`)
- Creates the `users` table storing `id` (auto-incrementing serial), `email` (indexed, unique, lowercase), `password_hash`, `full_name`, and `created_at`.
- Sets up an index on email for sub-millisecond query search speeds during logins.

### 2. Security & Hashing (`backend/auth.py`)
- **Bcrypt Password Salting**: Encrypts raw passwords using salted bcrypt hashes before storing them in PostgreSQL. 
- **Stateless JWT Tokens**: Generates JWT access tokens with an adjustable expiration duration containing user identification payloads.

### 3. Backend Endpoints (`backend/main.py`)
- `POST /api/auth/register`: Performs structural email validation, duplicate user checks, hashes passwords, inserts records into the database, and returns the newly created user object.
- `POST /api/auth/login`: Queries user details from the database by email, verifies password validity against the database hash, signs a token, and returns a JSON payload containing the JWT token.
- `GET /api/auth/me`: Decodes JWT tokens passed through Authorization Headers to return the active user's credentials.
- **Static Assets Serving**: FastAPI is configured to serve the `frontend/` directory directly, resolving CORS issues.

### 4. Interactive Frontend User Interface
- **Dynamic Auth Transitions**: Allows users to seamlessly switch between the "Sign In" and "Sign Up" views inside a single glassmorphic card without full page refreshes.
- **Show/Hide Password toggles**: Toggles the password fields on both forms with interactive, contextual SVG icons.
- **Client-Side Validations**: Checks emails for format correctness and enforces a minimum password length of 6 characters before requesting backend resources.
- **Asynchronous AJAX Fetch client**: Performs non-blocking requests to backend API routes and displays animated loaders.
- **Toast Notifications**: Built-in notification component for displaying success, info, and error banners.
- **Dashboard Shield**: Contains blocking scripts preventing unauthenticated users from seeing dashboard elements, automatically verifying token validity, and handling logouts.

---

## 🛠️ Installation & Setup

Follow these steps to run TicketFlow on your local machine:

### 1. Database Setup (Supabase)
1. Go to [Supabase](https://supabase.com) and sign in or sign up.
2. Create a new project (e.g., `TicketFlow`).
3. Once the project is provisioned, go to **Project Settings** (gear icon at the bottom of the sidebar) -> **Database**.
4. Scroll down to the **Connection Info** section and look for **Connection string**.
5. Select the **URI** tab. Copy the connection string. It will look similar to this:
   `postgresql://postgres.[your-project-ref]:[your-password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require`
   *(Note: Using the connection pooler on port `6543` is highly recommended for backend integrations).*

### 2. Configure Environment
1. Copy `.env.example` into a new file named `.env`:
   ```bash
   cp .env.example .env
   ```
2. Paste your copied Supabase connection URI into the `DATABASE_URL` field inside `.env`. Be sure to replace `[your-password]` with your actual database password:
   ```ini
   DATABASE_URL=postgresql://postgres.exampleprojectref:my_actual_password@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```
   *(Note: The Python backend automatically runs `schema.sql` on startup to build the required tables in your Supabase database if they don't already exist).*

### 3. Backend & Environment Initialization
1. In your project root, create a Python virtual environment:
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment:
   - **Windows (PowerShell)**: `.venv\Scripts\Activate.ps1`
   - **Windows (CMD)**: `.venv\Scripts\activate.bat`
   - **macOS / Linux**: `source .venv/bin/activate`
3. Install the dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

### 4. Run the Application
1. Start the server using Uvicorn:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```
2. Open your web browser and navigate to:
   **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🔒 Security Recommendations for Production
- Change the `JWT_SECRET` key inside your `.env` file to a long, random hexadecimal string (`openssl rand -hex 32`).
- Never check `.env` configurations or SQLite/log files into public version control.
