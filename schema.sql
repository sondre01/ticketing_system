-- Database schema for the Khin Ticket System

-- Create Schema for scoping the Ticketing System
CREATE SCHEMA IF NOT EXISTS ticketing_system;

-- Users table within the custom schema
CREATE TABLE IF NOT EXISTS ticketing_system.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' NOT NULL, -- 'admin' or 'user'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ensure role column exists if table was already created
ALTER TABLE ticketing_system.users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user';
ALTER TABLE ticketing_system.users ADD COLUMN IF NOT EXISTS department VARCHAR(100) DEFAULT 'General';
ALTER TABLE ticketing_system.users ADD COLUMN IF NOT EXISTS position VARCHAR(100) DEFAULT 'Employee';

-- Default first registered user to admin
UPDATE ticketing_system.users SET role = 'admin', department = 'Information Technology', position = 'Tech Lead' WHERE id = 1;

-- Index for faster login lookups by email
CREATE INDEX IF NOT EXISTS idx_users_email ON ticketing_system.users(email);

-- Tickets table
CREATE TABLE IF NOT EXISTS ticketing_system.tickets (
    id SERIAL PRIMARY KEY,
    ticket_code VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    requester_email VARCHAR(255) NOT NULL,
    requester_name VARCHAR(100),
    requester_id INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL,
    source VARCHAR(50) DEFAULT 'email',           -- 'email' or 'portal'
    status VARCHAR(50) DEFAULT 'open',            -- 'open', 'in_progress', 'resolved', 'closed'
    priority VARCHAR(20) DEFAULT 'medium',        -- 'low', 'medium', 'high', 'urgent'
    assigned_to INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL,
    email_message_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ensure requester_id column exists if table was already created
ALTER TABLE ticketing_system.tickets ADD COLUMN IF NOT EXISTS requester_id INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL;

-- Indexes for efficient ticket searching, filtering and sorting
CREATE INDEX IF NOT EXISTS idx_tickets_status ON ticketing_system.tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON ticketing_system.tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tickets_requester_id ON ticketing_system.tickets(requester_id);
CREATE INDEX IF NOT EXISTS idx_tickets_ticket_code ON ticketing_system.tickets(ticket_code);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON ticketing_system.tickets(created_at DESC);

-- Ticket Comments / Internal Activity table
CREATE TABLE IF NOT EXISTS ticketing_system.ticket_comments (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES ticketing_system.tickets(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES ticketing_system.users(id) ON DELETE SET NULL,
    comment_text TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comments_ticket_id ON ticketing_system.ticket_comments(ticket_id);

