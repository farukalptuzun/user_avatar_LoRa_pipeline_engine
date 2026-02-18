"""Database models and MongoDB access"""

from app.database.models import (
    USERS_COLLECTION,
    JOBS_COLLECTION,
    TrainingStatus,
    JobStatus,
    user_doc,
    job_doc,
)

__all__ = [
    "USERS_COLLECTION",
    "JOBS_COLLECTION",
    "TrainingStatus",
    "JobStatus",
    "user_doc",
    "job_doc",
]
