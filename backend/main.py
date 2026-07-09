import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.config import HOST, PORT
from backend.database import init_db_pool, close_db_pool, initialize_database, get_db_cursor
from backend.auth import hash_password, verify_password, create_access_token, decode_access_token

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticketing_system.main")

# FastAPI Lifespan Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Starting up backend server...")
    try:
        init_db_pool()
        initialize_database()
    except Exception as e:
        logger.error(f"Startup database initialization failed: {e}")
        # Note: We don't crash the server immediately, but database requests will fail.
    yield
    # Shutdown tasks
    logger.info("Shutting down backend server...")
    close_db_pool()

app = FastAPI(
    title="Ticketing System API",
    description="Python + PostgreSQL backend for Ticketing System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware (allows local HTML files to connect if opened directly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas for Request/Response
class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=100)

class LoginRequest(BaseModel):
    email: str
    password: str

# Token Security Dependency
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token payload.",
        )
    
    # Query database to get latest user details
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute("SELECT id, email, full_name, created_at FROM ticketing_system.users WHERE id = %s;", (user_id,))
            user = cur.fetchone()
    except Exception as e:
        logger.error(f"Database error during token validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection error."
        )
        
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists.",
        )
        
    # Format datetimes to ISO format for JSON compatibility
    if user.get("created_at"):
        user["created_at"] = user["created_at"].isoformat()
        
    return user

# --- API Routes ---

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    full_name = req.full_name.strip()
    
    if "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format."
        )
        
    # Hash password
    pwd_hash = hash_password(req.password)
    
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if email is already taken
            cur.execute("SELECT id FROM ticketing_system.users WHERE email = %s;", (email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this email address already exists."
                )
            
            # Insert new user
            cur.execute(
                "INSERT INTO ticketing_system.users (email, password_hash, full_name) VALUES (%s, %s, %s) RETURNING id, email, full_name;",
                (email, pwd_hash, full_name)
            )
            new_user = cur.fetchone()
            return {
                "message": "User registered successfully",
                "user": new_user
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user. Database error."
        )

@app.post("/api/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    
    try:
        with get_db_cursor(commit=False) as cur:
            # Query user
            cur.execute("SELECT * FROM ticketing_system.users WHERE email = %s;", (email,))
            user = cur.fetchone()
    except Exception as e:
        logger.error(f"Login database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed."
        )
        
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
        
    # Generate token
    token_data = {"sub": str(user["id"]), "email": user["email"]}
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"]
        }
    }

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "user": current_user
    }

# Serving frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info(f"Serving frontend static files from: {frontend_dir}")
else:
    logger.warning(f"Frontend static files directory not found at {frontend_dir}. Make sure you create it.")
