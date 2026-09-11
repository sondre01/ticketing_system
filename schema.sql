-- Database schema for the Khin Ticket System

-- Create Schema for scoping the Ticketing System
CREATE SCHEMA IF NOT EXISTS ticketing_system;

-- Users table within the custom schema
CREATE TABLE IF NOT EXISTS ticketing_system.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(30) DEFAULT 'employee' NOT NULL, -- 'super_admin', 'tech_member', 'dept_agent', 'employee'
    department VARCHAR(100) DEFAULT 'General',
    position VARCHAR(100) DEFAULT 'Employee',
    can_manage_departments BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ensure columns exist if table was already created
ALTER TABLE ticketing_system.users ADD COLUMN IF NOT EXISTS role VARCHAR(30) DEFAULT 'employee';
ALTER TABLE ticketing_system.users ADD COLUMN IF NOT EXISTS department VARCHAR(100) DEFAULT 'General';
ALTER TABLE ticketing_system.users ADD COLUMN IF NOT EXISTS position VARCHAR(100) DEFAULT 'Employee';
ALTER TABLE ticketing_system.users ADD COLUMN IF NOT EXISTS can_manage_departments BOOLEAN DEFAULT FALSE;

-- Default first registered user or admin to super_admin
UPDATE ticketing_system.users SET role = 'super_admin', can_manage_departments = TRUE WHERE id = 1 OR role = 'admin';
UPDATE ticketing_system.users SET role = 'tech_member' WHERE role = 'agent';
UPDATE ticketing_system.users SET role = 'employee' WHERE role IN ('customer', 'user');

-- Index for faster login lookups by email
CREATE INDEX IF NOT EXISTS idx_users_email ON ticketing_system.users(email);

-- Departments table
CREATE TABLE IF NOT EXISTS ticketing_system.departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed default departments if not present
INSERT INTO ticketing_system.departments (name, description)
VALUES 
    ('Information Technology', 'IT infrastructure, hardware, network, software tools, and account provisioning'),
    ('Human Resources', 'HR inquiries, employee onboarding, benefits, leave, and workplace relations'),
    ('Finance & Accounting', 'Payroll, expense reimbursement, billing, procurement, and budgets'),
    ('Operations & Facilities', 'Building access, maintenance, office equipment, and logistics'),
    ('General / Administrative', 'General administrative assistance, inquiries, and company services')
ON CONFLICT (name) DO NOTHING;

-- Tickets table
CREATE TABLE IF NOT EXISTS ticketing_system.tickets (
    id SERIAL PRIMARY KEY,
    ticket_code VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    requester_email VARCHAR(255) NOT NULL,
    requester_name VARCHAR(100),
    requester_id INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL,
    department_id INTEGER REFERENCES ticketing_system.departments(id) ON DELETE SET NULL,
    department_name VARCHAR(100) DEFAULT 'Information Technology',
    source VARCHAR(50) DEFAULT 'portal',           -- 'email' or 'portal'
    status VARCHAR(50) DEFAULT 'open',            -- 'open', 'in_progress', 'resolved', 'closed'
    priority VARCHAR(20) DEFAULT 'medium',        -- 'low', 'medium', 'high', 'urgent'
    assigned_to INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL,
    email_message_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ensure department columns exist on tickets
ALTER TABLE ticketing_system.tickets ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES ticketing_system.departments(id) ON DELETE SET NULL;
ALTER TABLE ticketing_system.tickets ADD COLUMN IF NOT EXISTS department_name VARCHAR(100) DEFAULT 'Information Technology';
ALTER TABLE ticketing_system.tickets ADD COLUMN IF NOT EXISTS requester_id INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL;

-- Indexes for efficient ticket searching, filtering and sorting
CREATE INDEX IF NOT EXISTS idx_tickets_status ON ticketing_system.tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON ticketing_system.tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tickets_requester_id ON ticketing_system.tickets(requester_id);
CREATE INDEX IF NOT EXISTS idx_tickets_dept_id ON ticketing_system.tickets(department_id);
CREATE INDEX IF NOT EXISTS idx_tickets_ticket_code ON ticketing_system.tickets(ticket_code);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON ticketing_system.tickets(created_at DESC);

-- Ticket Comments / Activity table
CREATE TABLE IF NOT EXISTS ticketing_system.ticket_comments (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES ticketing_system.tickets(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL,
    comment_text TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comments_ticket_id ON ticketing_system.ticket_comments(ticket_id);

-- Department Access Restrictions table
-- Allows managers to restrict specific users from raising tickets to certain departments
CREATE TABLE IF NOT EXISTS ticketing_system.department_restrictions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES ticketing_system.users(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES ticketing_system.departments(id) ON DELETE CASCADE,
    restricted_by INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, department_id)
);

CREATE INDEX IF NOT EXISTS idx_dept_restrictions_user_id ON ticketing_system.department_restrictions(user_id);
CREATE INDEX IF NOT EXISTS idx_dept_restrictions_dept_id ON ticketing_system.department_restrictions(department_id);

