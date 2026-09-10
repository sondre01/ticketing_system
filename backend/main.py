import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.config import HOST, PORT, TECH_ACCESS_KEY
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
    title="Khin Ticket API",
    description="Python + PostgreSQL backend for Khin Ticket",
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
    department: str | None = Field(default="General", max_length=100)
    position: str | None = Field(default="Employee", max_length=100)
    role: str = Field(default="customer")
    tech_passcode: str | None = Field(default=None)

class LoginRequest(BaseModel):
    email: str
    password: str

class TicketCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(default="")
    priority: str = Field(default="medium")
    requester_email: str | None = None
    requester_name: str | None = None

class TicketUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: int | None = None

class CommentCreateRequest(BaseModel):
    comment_text: str = Field(..., min_length=1)
    is_internal: bool = True

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
            cur.execute("SELECT id, email, full_name, role, department, position, created_at FROM ticketing_system.users WHERE id = %s;", (user_id,))
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

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required for this action."
        )
    return current_user

def generate_ticket_code(cur) -> str:
    cur.execute("SELECT MAX(id) as max_id FROM ticketing_system.tickets;")
    res = cur.fetchone()
    next_id = (res["max_id"] or 0) + 1
    return f"KT-{1000 + next_id}"

class VerifyPasscodeRequest(BaseModel):
    passcode: str = Field(..., min_length=1)

# --- Auth Routes ---

@app.post("/api/auth/verify-passcode")
def verify_tech_passcode(req: VerifyPasscodeRequest):
    cleaned_passcode = req.passcode.strip()
    if cleaned_passcode == TECH_ACCESS_KEY:
        return {"valid": True, "message": "Tech Security Passcode verified successfully."}
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid Tech Security Passcode. Access denied."
    )

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    full_name = req.full_name.strip()
    department = (req.department or "General").strip()
    position = (req.position or "Employee").strip()
    requested_role = req.role.strip().lower() if req.role else "customer"
    tech_passcode = (req.tech_passcode or "").strip()

    if "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format."
        )

    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    # Keyword analysis for Department and Position
    dept_lower = department.lower()
    pos_lower = position.lower()

    tech_keywords = [
        "tech", "it", "information technology", "developer", "engineer", "sysadmin", 
        "devops", "systems", "network", "software", "infrastructure", "support", "helpdesk"
    ]
    lead_keywords = [
        "manager", "lead", "head", "director", "supervisor", "chief", "cto", "cio", "vp"
    ]

    is_tech_dept = any(kw in dept_lower for kw in tech_keywords)
    is_tech_pos = any(kw in pos_lower for kw in tech_keywords)
    is_lead_pos = any(kw in pos_lower for kw in lead_keywords)
    claims_tech_role = requested_role in ("admin", "agent", "operator")

    # Determine final role with validation and fixed passcode enforcement
    if claims_tech_role or tech_passcode:
        # User is requesting tech team / admin status or provided a tech passcode
        if not tech_passcode or tech_passcode != TECH_ACCESS_KEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or missing Tech Department passcode. Only authorized tech personnel with the security key can register for Tech Team access."
            )

        # Passcode is valid! Check if non-tech department trying to claim tech role
        non_tech_depts = ["hr", "human resources", "finance", "accounting", "sales", "marketing", "legal"]
        if any(nt in dept_lower for nt in non_tech_depts) and not is_tech_pos:
            final_role = "customer"
        elif requested_role == "admin" or (is_lead_pos and requested_role != "agent"):
            final_role = "admin"
        else:
            final_role = "agent"
    else:
        # Regular corporate employee / requester without tech role or passcode
        final_role = "customer"

    pwd_hash = hash_password(req.password)

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("SELECT id FROM ticketing_system.users WHERE email = %s;", (email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this email address already exists."
                )

            cur.execute(
                """
                INSERT INTO ticketing_system.users (email, password_hash, full_name, role, department, position) 
                VALUES (%s, %s, %s, %s, %s, %s) 
                RETURNING id, email, full_name, role, department, position;
                """,
                (email, pwd_hash, full_name, final_role, department, position)
            )
            new_user = cur.fetchone()

            # Generate access token immediately for auto-login
            token_data = {"sub": str(new_user["id"]), "email": new_user["email"], "role": final_role}
            access_token = create_access_token(data=token_data)

            return {
                "message": "User registered successfully",
                "access_token": access_token,
                "token_type": "bearer",
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

    # Generate access token
    token_data = {"sub": str(user["id"]), "email": user["email"], "role": user["role"]}
    access_token = create_access_token(data=token_data)

    user_data = {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "department": user.get("department", "General"),
        "position": user.get("position", "Employee"),
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None
    }

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "user": current_user
    }

# --- Team Members Endpoint ---

@app.get("/api/team")
def get_team_members(current_user: dict = Depends(get_current_user)):
    """Returns list of tech team members for ticket assignment."""
    user_role = current_user.get("role", "customer")
    if user_role in ("customer", "user"):
        raise HTTPException(status_code=403, detail="Requesters cannot view internal team members.")

    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute("SELECT id, email, full_name, role, department, position, created_at FROM ticketing_system.users WHERE role IN ('admin', 'agent') ORDER BY full_name ASC;")
            members = cur.fetchall()
            for m in members:
                if m.get("created_at"):
                    m["created_at"] = m["created_at"].isoformat()
            return {"members": members}
    except Exception as e:
        logger.error(f"Failed to fetch team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch team members.")

# --- Ticket Management Endpoints ---

@app.get("/api/tickets")
def list_tickets(
    status_filter: str | None = None,
    priority_filter: str | None = None,
    current_user: dict = Depends(get_current_user)
):
    """
    List tickets.
    - Admins see all tickets.
    - Tech operators ('agent') see tickets assigned to them or unassigned.
    - Customers ('customer') see ONLY their own tickets.
    """
    query = """
        SELECT 
            t.id, t.ticket_code, t.title, t.description, t.requester_email, 
            t.requester_name, t.requester_id, t.source, t.status, t.priority, t.assigned_to,
            t.created_at, t.updated_at,
            u.full_name AS assignee_name, u.email AS assignee_email
        FROM ticketing_system.tickets t
        LEFT JOIN ticketing_system.users u ON t.assigned_to = u.id
        WHERE 1=1
    """
    params = []

    user_role = current_user.get("role", "customer")

    if user_role in ("customer", "user"):
        query += " AND (t.requester_id = %s OR t.requester_email = %s)"
        params.extend([current_user["id"], current_user["email"]])
    elif user_role in ("agent", "operator"):
        query += " AND (t.assigned_to = %s OR t.assigned_to IS NULL)"
        params.append(current_user["id"])
    # Admins see all

    if status_filter:
        query += " AND t.status = %s"
        params.append(status_filter.lower())

    if priority_filter:
        query += " AND t.priority = %s"
        params.append(priority_filter.lower())

    query += " ORDER BY t.created_at DESC;"

    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(query, tuple(params))
            tickets = cur.fetchall()
            for item in tickets:
                if item.get("created_at"):
                    item["created_at"] = item["created_at"].isoformat()
                if item.get("updated_at"):
                    item["updated_at"] = item["updated_at"].isoformat()
            return {"tickets": tickets}
    except Exception as e:
        logger.error(f"Error fetching tickets: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tickets.")

@app.post("/api/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(req: TicketCreateRequest, current_user: dict = Depends(get_current_user)):
    """Creates a new ticket (used by Customers to raise technical requests)."""
    user_role = current_user.get("role", "customer")
    
    if user_role in ("customer", "user"):
        requester_email = current_user["email"]
        requester_name = current_user["full_name"]
        requester_id = current_user["id"]
    else:
        requester_email = (req.requester_email or current_user["email"]).strip().lower()
        requester_name = (req.requester_name or current_user["full_name"]).strip()
        requester_id = current_user["id"]

    try:
        with get_db_cursor(commit=True) as cur:
            ticket_code = generate_ticket_code(cur)
            cur.execute(
                """
                INSERT INTO ticketing_system.tickets 
                (ticket_code, title, description, requester_email, requester_name, requester_id, source, priority, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'portal', %s, 'open')
                RETURNING id, ticket_code, title, description, requester_email, requester_name, requester_id, source, priority, status, created_at;
                """,
                (
                    ticket_code,
                    req.title.strip(),
                    req.description.strip(),
                    requester_email,
                    requester_name,
                    requester_id,
                    req.priority.lower()
                )
            )
            ticket = cur.fetchone()
            if ticket.get("created_at"):
                ticket["created_at"] = ticket["created_at"].isoformat()
            return {"message": "Ticket raised successfully", "ticket": ticket}
    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket.")

@app.get("/api/tickets/{ticket_id}")
def get_ticket_details(ticket_id: int, current_user: dict = Depends(get_current_user)):
    """Fetches ticket details and its comments thread (filters out internal notes for customers)."""
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT 
                    t.id, t.ticket_code, t.title, t.description, t.requester_email, 
                    t.requester_name, t.requester_id, t.source, t.status, t.priority, t.assigned_to,
                    t.created_at, t.updated_at,
                    u.full_name AS assignee_name, u.email AS assignee_email
                FROM ticketing_system.tickets t
                LEFT JOIN ticketing_system.users u ON t.assigned_to = u.id
                WHERE t.id = %s;
                """,
                (ticket_id,)
            )
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found.")
            
            user_role = current_user.get("role", "customer")

            # Check permissions
            if user_role in ("customer", "user"):
                if ticket.get("requester_id") != current_user["id"] and ticket.get("requester_email") != current_user["email"]:
                    raise HTTPException(status_code=403, detail="You can only view your own tickets.")
            elif user_role in ("agent", "operator"):
                if ticket["assigned_to"] is not None and ticket["assigned_to"] != current_user["id"]:
                    raise HTTPException(status_code=403, detail="Not authorized to view this ticket.")

            if ticket.get("created_at"):
                ticket["created_at"] = ticket["created_at"].isoformat()
            if ticket.get("updated_at"):
                ticket["updated_at"] = ticket["updated_at"].isoformat()

            # For customers, hide internal tech notes!
            internal_filter = "AND c.is_internal = FALSE" if user_role in ("customer", "user") else ""

            cur.execute(
                f"""
                SELECT 
                    c.id, c.comment_text, c.is_internal, c.created_at,
                    u.full_name AS author_name, u.email AS author_email, u.role AS author_role
                FROM ticketing_system.ticket_comments c
                LEFT JOIN ticketing_system.users u ON c.user_id = u.id
                WHERE c.ticket_id = %s {internal_filter}
                ORDER BY c.created_at ASC;
                """,
                (ticket_id,)
            )
            comments = cur.fetchall()
            for c in comments:
                if c.get("created_at"):
                    c["created_at"] = c["created_at"].isoformat()

            ticket["comments"] = comments
            return {"ticket": ticket}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ticket details: {e}")
        raise HTTPException(status_code=500, detail="Failed to load ticket details.")

@app.patch("/api/tickets/{ticket_id}")
def update_ticket(
    ticket_id: int, 
    req: TicketUpdateRequest, 
    current_user: dict = Depends(get_current_user)
):
    """
    Update ticket status, priority, or assignee.
    - Tech member can update status.
    - Admin can update status, priority, and assigned_to.
    """
    user_role = current_user.get("role", "customer")
    if user_role in ("customer", "user"):
        raise HTTPException(status_code=403, detail="Requesters cannot reassign or change internal ticket properties.")

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("SELECT * FROM ticketing_system.tickets WHERE id = %s;", (ticket_id,))
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found.")

            is_admin = user_role == "admin"
            is_assignee = ticket["assigned_to"] == current_user["id"]

            if not is_admin and not is_assignee and ticket["assigned_to"] is not None:
                raise HTTPException(status_code=403, detail="You do not have permission to modify this ticket.")

            updates = []
            params = []

            if req.status:
                valid_statuses = ("open", "in_progress", "resolved", "closed")
                if req.status.lower() in valid_statuses:
                    updates.append("status = %s")
                    params.append(req.status.lower())

            # Only admin can reassign or change priority
            if is_admin:
                if req.priority:
                    valid_priorities = ("low", "medium", "high", "urgent")
                    if req.priority.lower() in valid_priorities:
                        updates.append("priority = %s")
                        params.append(req.priority.lower())
                
                if req.assigned_to is not None:
                    if req.assigned_to == 0:
                        updates.append("assigned_to = NULL")
                    else:
                        cur.execute("SELECT id FROM ticketing_system.users WHERE id = %s;", (req.assigned_to,))
                        if cur.fetchone():
                            updates.append("assigned_to = %s")
                            params.append(req.assigned_to)

            if not updates:
                return {"message": "No valid updates provided."}

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(ticket_id)

            set_clause = ", ".join(updates)
            cur.execute(f"UPDATE ticketing_system.tickets SET {set_clause} WHERE id = %s RETURNING id, ticket_code, status, priority, assigned_to, updated_at;", tuple(params))
            updated_ticket = cur.fetchone()
            if updated_ticket.get("updated_at"):
                updated_ticket["updated_at"] = updated_ticket["updated_at"].isoformat()

            return {"message": "Ticket updated successfully", "ticket": updated_ticket}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update ticket.")

@app.post("/api/tickets/{ticket_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(
    ticket_id: int, 
    req: CommentCreateRequest, 
    current_user: dict = Depends(get_current_user)
):
    """Add a response or note to a ticket."""
    user_role = current_user.get("role", "customer")
    
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("SELECT id, requester_id, requester_email FROM ticketing_system.tickets WHERE id = %s;", (ticket_id,))
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found.")

            # If customer, verify ownership and ensure comment is public (not internal)
            if user_role in ("customer", "user"):
                if ticket.get("requester_id") != current_user["id"] and ticket.get("requester_email") != current_user["email"]:
                    raise HTTPException(status_code=403, detail="You can only comment on your own tickets.")
                is_internal = False
            else:
                is_internal = req.is_internal

            cur.execute(
                """
                INSERT INTO ticketing_system.ticket_comments (ticket_id, user_id, comment_text, is_internal)
                VALUES (%s, %s, %s, %s)
                RETURNING id, comment_text, is_internal, created_at;
                """,
                (ticket_id, current_user["id"], req.comment_text.strip(), is_internal)
            )
            new_comment = cur.fetchone()
            if new_comment.get("created_at"):
                new_comment["created_at"] = new_comment["created_at"].isoformat()
            new_comment["author_name"] = current_user["full_name"]
            new_comment["author_email"] = current_user["email"]
            new_comment["author_role"] = user_role

            return {"message": "Comment added successfully", "comment": new_comment}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding comment to ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to add comment.")

@app.get("/api/dashboard/stats")
def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Computes live stats tailored to the user's role."""
    try:
        with get_db_cursor(commit=False) as cur:
            user_role = current_user.get("role", "customer")
            
            if user_role == "admin":
                cur.execute("SELECT COUNT(*) as total FROM ticketing_system.tickets;")
                total = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) as open FROM ticketing_system.tickets WHERE status = 'open';")
                open_count = cur.fetchone()["open"]
                cur.execute("SELECT COUNT(*) as in_progress FROM ticketing_system.tickets WHERE status = 'in_progress';")
                in_progress = cur.fetchone()["in_progress"]
                cur.execute("SELECT COUNT(*) as resolved FROM ticketing_system.tickets WHERE status IN ('resolved', 'closed');")
                resolved = cur.fetchone()["resolved"]
                cur.execute("SELECT COUNT(*) as unassigned FROM ticketing_system.tickets WHERE assigned_to IS NULL;")
                unassigned = cur.fetchone()["unassigned"]
            elif user_role in ("agent", "operator"):
                user_id = current_user["id"]
                cur.execute("SELECT COUNT(*) as total FROM ticketing_system.tickets WHERE assigned_to = %s OR assigned_to IS NULL;", (user_id,))
                total = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) as open FROM ticketing_system.tickets WHERE status = 'open' AND (assigned_to = %s OR assigned_to IS NULL);", (user_id,))
                open_count = cur.fetchone()["open"]
                cur.execute("SELECT COUNT(*) as in_progress FROM ticketing_system.tickets WHERE status = 'in_progress' AND assigned_to = %s;", (user_id,))
                in_progress = cur.fetchone()["in_progress"]
                cur.execute("SELECT COUNT(*) as resolved FROM ticketing_system.tickets WHERE status IN ('resolved', 'closed') AND assigned_to = %s;", (user_id,))
                resolved = cur.fetchone()["resolved"]
                unassigned = 0
            else:
                # Customer (Requester): only their tickets!
                user_id = current_user["id"]
                user_email = current_user["email"]
                cur.execute("SELECT COUNT(*) as total FROM ticketing_system.tickets WHERE requester_id = %s OR requester_email = %s;", (user_id, user_email))
                total = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) as open FROM ticketing_system.tickets WHERE (requester_id = %s OR requester_email = %s) AND status = 'open';", (user_id, user_email))
                open_count = cur.fetchone()["open"]
                cur.execute("SELECT COUNT(*) as in_progress FROM ticketing_system.tickets WHERE (requester_id = %s OR requester_email = %s) AND status = 'in_progress';", (user_id, user_email))
                in_progress = cur.fetchone()["in_progress"]
                cur.execute("SELECT COUNT(*) as resolved FROM ticketing_system.tickets WHERE (requester_id = %s OR requester_email = %s) AND status IN ('resolved', 'closed');", (user_id, user_email))
                resolved = cur.fetchone()["resolved"]
                unassigned = 0

            cur.execute("SELECT COUNT(*) as team_count FROM ticketing_system.users WHERE role IN ('admin', 'agent');")
            team_count = cur.fetchone()["team_count"]

            return {
                "total": total,
                "open": open_count,
                "in_progress": in_progress,
                "resolved": resolved,
                "unassigned": unassigned,
                "team_members": team_count,
                "user_role": user_role
            }
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard metrics.")

@app.post("/api/tickets/sync-emails")
def sync_emails(current_user: dict = Depends(get_current_user)):
    """Fetches unread emails from Gmail and converts them into tickets."""
    user_role = current_user.get("role", "customer")
    if user_role in ("customer", "user"):
        raise HTTPException(status_code=403, detail="Requesters cannot trigger email sync.")
    from backend.email_service import sync_gmail_tickets
    result = sync_gmail_tickets(mark_as_read=True)
    return result

# Serving frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info(f"Serving frontend static files from: {frontend_dir}")
else:
    logger.warning(f"Frontend static files directory not found at {frontend_dir}. Make sure you create it.")
