-- Database schema for the Ticketing System

-- Create Schema for scoping the Ticketing System
CREATE SCHEMA IF NOT EXISTS ticketing_system;

-- Users table within the custom schema
CREATE TABLE IF NOT EXISTS ticketing_system.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster login lookups by email
CREATE INDEX IF NOT EXISTS idx_users_email ON ticketing_system.users(email);
