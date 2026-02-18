"""FastAPI dependencies for database and shared resources"""

from typing import Generator
from pymongo import MongoClient
from pymongo.database import Database
from app.config.settings import settings
from app.database.models import USERS_COLLECTION, JOBS_COLLECTION

# Global MongoDB client
_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    """Get or create MongoDB client."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client


def get_db() -> Generator[Database, None, None]:
    """Dependency for getting MongoDB database (lora_avatar)."""
    client = get_mongo_client()
    db = client[settings.MONGODB_DB_NAME]
    try:
        yield db
    finally:
        pass  # Client is long-lived, no close per request


def get_database() -> Database:
    """Return database instance (for use in Celery tasks)."""
    client = get_mongo_client()
    return client[settings.MONGODB_DB_NAME]


def init_db():
    """Ensure database and collections exist (create collections if missing)."""
    db = get_database()
    existing = db.list_collection_names()
    if USERS_COLLECTION not in existing:
        db.create_collection(USERS_COLLECTION)
    if JOBS_COLLECTION not in existing:
        db.create_collection(JOBS_COLLECTION)
    # Indexes for common lookups
    db[USERS_COLLECTION].create_index("user_id", unique=True)
    db[JOBS_COLLECTION].create_index("job_id", unique=True)
    db[JOBS_COLLECTION].create_index("user_id")
