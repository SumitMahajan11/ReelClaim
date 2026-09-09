import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict, Tuple

from sqlalchemy import create_engine, Column, String, Text, Float, DateTime, JSON, Integer, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger("reelclaim.db")

Base = declarative_base()

class AuditRecord(Base):
    __tablename__ = "audits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    caption = Column(Text, nullable=False)
    promoted_site = Column(Text, nullable=True)
    override_url = Column(Text, nullable=True)
    claims = Column(JSON, nullable=True)
    crawl_status = Column(String(50), nullable=True)
    verdicts = Column(JSON, nullable=True)
    confidence_tier = Column(String(50), nullable=True)
    coverage_status = Column(String(50), nullable=True)
    summary_label = Column(Text, nullable=True)
    facts = Column(JSON, nullable=True)
    status = Column(String(50), default="completed")
    submitter_token = Column(String(64), nullable=True, index=True)
    feedback = Column(JSON, nullable=True, default=list)

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    rate_limit_per_hour = Column(Integer, default=60, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


engine = None
SessionLocal = None
_db_initialized = False

def init_db() -> bool:
    """
    Initializes database engine and sessionmaker if DATABASE_URL is provided in environment.
    If DATABASE_URL is unset, degrades gracefully to 'persistence disabled' and logs a warning.
    """
    global engine, SessionLocal, _db_initialized
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.strip():
        logger.warning("DATABASE_URL environment variable is unset. Audit persistence is disabled.")
        return False

    db_url = database_url.strip()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True if not db_url.startswith("sqlite") else False)
        
        # Run Alembic migrations automatically on startup if alembic.ini is present
        try:
            from alembic.config import Config
            from alembic import command
            alembic_ini_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
            if os.path.exists(alembic_ini_path):
                alembic_cfg = Config(alembic_ini_path)
                alembic_cfg.set_main_option("sqlalchemy.url", db_url)
                command.upgrade(alembic_cfg, "head")
                logger.info("Alembic migrations applied successfully.")
            else:
                Base.metadata.create_all(bind=engine)
        except Exception as migration_err:
            logger.warning(f"Alembic migration execution note ({migration_err}). Ensuring tables via create_all.")
            Base.metadata.create_all(bind=engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _db_initialized = True
        logger.info("Database initialized successfully.")
        return True
    except Exception as e:
        logger.warning(f"Database initialization failed ({e}). Audit persistence is disabled.")
        _db_initialized = False
        return False

def get_db_session() -> Optional[Session]:
    if not _db_initialized or SessionLocal is None:
        return None
    try:
        return SessionLocal()
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        return None

def to_jsonable(obj: Any) -> Any:
    """Recursively converts Pydantic models, datetimes, and custom objects to JSON-serializable primitives."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [to_jsonable(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return json.loads(json.dumps(obj.dict(), default=str))
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    return obj

# Fallback in-memory audit store when DB persistence is disabled: Dict[audit_id, dict]
_in_memory_audits: Dict[str, dict] = {}

def save_audit_record(
    caption: str,
    promoted_site: Optional[str],
    override_url: Optional[str],
    claims: List[Any],
    crawl_status: Optional[str],
    check_result: Optional[Any],
    facts: Optional[List[Any]] = None,
    submitter_token: Optional[str] = None
) -> Optional[str]:
    """
    Persists a completed audit run result and gathered facts into the database.
    Returns the audit record ID, or fallback in-memory ID if database is uninitialized.
    """
    audit_id = str(uuid.uuid4())
    created_at_iso = datetime.now(timezone.utc).isoformat()
    claims_data = to_jsonable(claims) if claims else []
    facts_data = to_jsonable(facts) if facts else None

    verdicts_data = None
    confidence_tier = None
    coverage_status = None
    summary_label = None

    if check_result:
        confidence_tier = getattr(check_result, "confidence_tier", None)
        coverage_status = getattr(check_result, "coverage_status", None)
        summary_label = getattr(check_result, "summary_label", None)
        verdicts = getattr(check_result, "verdicts", [])
        if verdicts:
            verdicts_data = to_jsonable(verdicts)

    # Always cache in in-memory store
    _in_memory_audits[audit_id] = {
        "id": audit_id,
        "created_at": created_at_iso,
        "caption": caption,
        "promoted_site": promoted_site,
        "override_url": override_url,
        "claims": claims_data,
        "crawl_status": crawl_status,
        "confidence_tier": confidence_tier,
        "coverage_status": coverage_status,
        "summary_label": summary_label,
        "verdicts": verdicts_data or [],
        "facts": facts_data or [],
        "status": "completed",
        "submitter_token": submitter_token,
        "feedback": []
    }

    session = get_db_session()
    if not session:
        return audit_id

    try:
        record = AuditRecord(
            id=audit_id,
            created_at=datetime.now(timezone.utc),
            caption=caption,
            promoted_site=promoted_site,
            override_url=override_url,
            claims=claims_data,
            crawl_status=crawl_status,
            verdicts=verdicts_data,
            confidence_tier=confidence_tier,
            coverage_status=coverage_status,
            summary_label=summary_label,
            facts=facts_data,
            status="completed",
            submitter_token=submitter_token,
            feedback=[]
        )
        session.add(record)
        session.commit()
        session.close()
        return audit_id
    except Exception as e:
        logger.error(f"Failed to persist audit record to DB: {e}")
        if session:
            session.rollback()
            session.close()
        return audit_id

def get_audit_record_by_id(audit_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches an audit record by ID from DB or in-memory fallback store.
    """
    session = get_db_session()
    if session:
        try:
            record = session.query(AuditRecord).filter(AuditRecord.id == audit_id).first()
            if record:
                data = {
                    "id": record.id,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "caption": record.caption,
                    "promoted_site": record.promoted_site,
                    "override_url": record.override_url,
                    "claims": record.claims or [],
                    "crawl_status": record.crawl_status,
                    "confidence_tier": record.confidence_tier,
                    "coverage_status": record.coverage_status,
                    "summary_label": record.summary_label,
                    "verdicts": record.verdicts or [],
                    "facts": record.facts or [],
                    "status": record.status,
                    "submitter_token": record.submitter_token,
                    "feedback": record.feedback or []
                }
                session.close()
                return data
            session.close()
        except Exception as e:
            logger.error(f"Failed to fetch audit by ID {audit_id} from DB: {e}")
            if session:
                session.close()

    return _in_memory_audits.get(audit_id)

def save_audit_feedback(
    audit_id: str,
    feedback_data: Dict[str, Any],
    submitter_token: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Persists user feedback on a specific audit verdict.
    Auth-gated: If audit was submitted with a submitter_token, verifies caller matches.
    Returns (success, feedback_id, message).
    """
    session = get_db_session()
    feedback_id = str(uuid.uuid4())
    created_at_iso = datetime.now(timezone.utc).isoformat()

    entry = {
        "feedback_id": feedback_id,
        "created_at": created_at_iso,
        "claim_index": feedback_data.get("claim_index"),
        "feedback_type": feedback_data.get("feedback_type", "wrong_verdict"),
        "expected_verdict": feedback_data.get("expected_verdict"),
        "user_notes": feedback_data.get("user_notes"),
        "submitter_token": submitter_token
    }

    if not session:
        mem_record = _in_memory_audits.get(audit_id)
        if not mem_record:
            return False, None, f"Audit '{audit_id}' not found."

        if mem_record.get("submitter_token") and submitter_token:
            if mem_record["submitter_token"] != submitter_token.strip():
                return False, None, "Forbidden: Only the original audit submitter can flag verdicts on this audit."

        current_fb = list(mem_record.get("feedback") or [])
        current_fb.append(entry)
        mem_record["feedback"] = current_fb
        return True, feedback_id, "Feedback recorded successfully."

    try:
        record = session.query(AuditRecord).filter(AuditRecord.id == audit_id).first()
        if not record:
            session.close()
            # Check in memory fallback
            mem_record = _in_memory_audits.get(audit_id)
            if not mem_record:
                return False, None, f"Audit '{audit_id}' not found."
            if mem_record.get("submitter_token") and submitter_token:
                if mem_record["submitter_token"] != submitter_token.strip():
                    return False, None, "Forbidden: Only the original audit submitter can flag verdicts on this audit."
            current_fb = list(mem_record.get("feedback") or [])
            current_fb.append(entry)
            mem_record["feedback"] = current_fb
            return True, feedback_id, "Feedback recorded successfully."

        # Submitter token validation gate
        if record.submitter_token and submitter_token:
            if record.submitter_token != submitter_token.strip():
                session.close()
                return False, None, "Forbidden: Only the original audit submitter can flag verdicts on this audit."

        current_feedback = list(record.feedback or [])
        current_feedback.append(entry)
        record.feedback = current_feedback

        session.commit()
        session.close()

        if audit_id in _in_memory_audits:
            _in_memory_audits[audit_id]["feedback"] = current_feedback

        return True, feedback_id, "Feedback recorded successfully."
    except Exception as e:
        logger.error(f"Failed to save feedback for audit {audit_id}: {e}")
        if session:
            session.rollback()
            session.close()
        return False, None, str(e)

def list_recent_audit_records(limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    Lists recent audit records paginated, ordered by creation date descending.
    """
    session = get_db_session()
    if not session:
        return {"total": 0, "limit": limit, "offset": offset, "audits": [], "persistence": "disabled"}

    try:
        total = session.query(AuditRecord).count()
        records = (
            session.query(AuditRecord)
            .order_by(AuditRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = []
        for record in records:
            items.append({
                "id": record.id,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "caption": record.caption,
                "promoted_site": record.promoted_site,
                "crawl_status": record.crawl_status,
                "confidence_tier": record.confidence_tier,
                "coverage_status": record.coverage_status,
                "summary_label": record.summary_label,
                "total_claims": len(record.claims or []),
                "status": record.status
            })
        session.close()
        return {"total": total, "limit": limit, "offset": offset, "audits": items}
    except Exception as e:
        logger.error(f"Failed to list audit records: {e}")
        if session:
            session.close()
        return {"total": 0, "limit": limit, "offset": offset, "audits": [], "error": str(e)}

def save_api_key_record(key_hash: str, name: str, rate_limit_per_hour: int = 10) -> Optional[str]:
    """
    Saves an API key hash record into the database.
    Returns key ID or None if DB disabled or save fails.
    """
    session = get_db_session()
    if not session:
        return None

    try:
        key_id = str(uuid.uuid4())
        record = ApiKey(
            id=key_id,
            key_hash=key_hash,
            name=name,
            rate_limit_per_hour=rate_limit_per_hour,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(record)
        session.commit()
        session.close()
        return key_id
    except Exception as e:
        logger.error(f"Failed to save API key record: {e}")
        if session:
            session.rollback()
            session.close()
        return None

def get_api_key_by_hash(key_hash: str) -> Optional[Dict[str, Any]]:
    """
    Looks up an API key record by its SHA-256 hash.
    Returns dictionary or None if not found or DB disabled.
    """
    session = get_db_session()
    if not session:
        return None

    try:
        record = session.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
        if not record:
            session.close()
            return None

        data = {
            "id": record.id,
            "key_hash": record.key_hash,
            "name": record.name,
            "rate_limit_per_hour": record.rate_limit_per_hour,
            "is_active": record.is_active,
            "created_at": record.created_at.isoformat() if record.created_at else None
        }
        session.close()
        return data
    except Exception as e:
        logger.error(f"Failed to lookup API key: {e}")
        if session:
            session.close()
        return None

