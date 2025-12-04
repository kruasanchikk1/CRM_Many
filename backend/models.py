# models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class Task(BaseModel):
    description: str
    deadline: str
    assignee: str
    priority: str

class Analysis(BaseModel):
    summary: str
    tasks: List[Task]
    key_points: List[str]
    decisions: List[str]

class JobResponse(BaseModel):
    job_id: str
    filename: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    transcript: Optional[str] = None
    transcript_chars: Optional[int] = None
    analysis: Optional[Analysis] = None

class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int