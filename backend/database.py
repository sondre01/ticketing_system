import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import logging
from contextlib import contextmanager
from backend.config import DATABASE_URL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticketing_system.database")

_pool = None

def init_db_pool():
    global _pool
    if _pool is not None:
        return
    try:
        # Initialize a connection pool (min 1, max 10 connections)
        _pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            dsn=DATABASE_URL
        )
        logger.info("PostgreSQL connection pool initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
        logger.error("Please ensure PostgreSQL is running and DATABASE_URL in .env is correct.")
        raise e

def close_db_pool():
    global _pool
    if _pool:
        _pool.closeall()
        logger.info("PostgreSQL connection pool closed.")
        _pool = None

@contextmanager
def get_db_connection():
    global _pool
    if _pool is None:
        init_db_pool()
    
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)

@contextmanager
def get_db_cursor(commit=True):
    with get_db_connection() as conn:
        # RealDictCursor returns rows as python dicts where keys are column names
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                yield cur
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database transaction error (rolled back): {e}")
                raise e

def initialize_database():
    """Reads schema.sql and runs it to set up tables if they don't exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    if not os.path.exists(schema_path):
        logger.warning(f"schema.sql not found at {schema_path}, skipping tables initialization.")
        return
        
    logger.info("Applying database schema...")
    try:
        with open(schema_path, "r") as f:
            schema_sql = f.read()
            
        with get_db_cursor(commit=True) as cur:
            cur.execute(schema_sql)
            logger.info("Database schema applied successfully.")
    except Exception as e:
        logger.error(f"Failed to apply database schema: {e}")
        raise e
