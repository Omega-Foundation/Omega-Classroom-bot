"""Database models and connection handling."""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import text
from app.config import Config

Base = declarative_base()

class User(Base):
    """Telegram user model."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    github_username = Column(String(255))
    github_token = Column(String(500))  # Store GitHub personal access token
    role = Column(String(20), nullable=False, default='student')  # 'student' or 'teacher'
    # Per-user notification settings (override app defaults if set)
    notify_threshold_hours = Column(Integer)  # if None, fallback to app settings
    notify_period_seconds = Column(Integer)   # if None, fallback to app settings
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    assignments = relationship('Assignment', back_populates='user')
    submissions = relationship('Submission', back_populates='user')
    ci_repositories = relationship('TrackedRepository', back_populates='user', cascade='all, delete-orphan')
    classroom_records = relationship('ClassroomAssignmentRecord', back_populates='teacher', cascade='all, delete-orphan')
    ci_repositories = relationship('TrackedRepository', back_populates='user', cascade='all, delete-orphan')

class Assignment(Base):
    """Assignment model."""
    __tablename__ = 'assignments'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    github_repo_name = Column(String(255), nullable=False)
    github_repo_url = Column(String(500))
    deadline = Column(DateTime, nullable=False)
    classroom_id = Column(String(255))
    classroom_assignment_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='assignments')
    submissions = relationship('Submission', back_populates='assignment', cascade='all, delete-orphan')

class Submission(Base):
    """Student submission tracking model."""
    __tablename__ = 'submissions'
    
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    github_repo_url = Column(String(500))
    last_commit_sha = Column(String(255))
    last_commit_date = Column(DateTime)
    is_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assignment = relationship('Assignment', back_populates='submissions')
    user = relationship('User', back_populates='submissions')

class TrackedRepository(Base):
    """Repository subscriptions for CI status tracking."""
    __tablename__ = 'tracked_repositories'
    __table_args__ = (UniqueConstraint('user_id', 'repo_full_name', name='uq_user_repo'),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    repo_full_name = Column(String(255), nullable=False)
    repo_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship('User', back_populates='ci_repositories')

class Notification(Base):
    """Notification tracking model."""
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    assignment_id = Column(Integer, ForeignKey('assignments.id'))
    notification_type = Column(String(50), nullable=False)  # 'deadline_warning', 'unsubmitted', etc.
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

class ClassroomAssignmentRecord(Base):
    """Snapshot records of classroom assignments fetched for teachers."""
    __tablename__ = 'classroom_assignment_records'
    
    id = Column(Integer, primary_key=True)
    teacher_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    classroom_id = Column(String(255))
    classroom_name = Column(String(255))
    assignment_id = Column(String(255))
    assignment_title = Column(String(255))
    assignment_url = Column(String(500))
    deadline = Column(DateTime)
    student_login = Column(String(255))
    student_display_login = Column(String(255))
    student_repo_url = Column(String(500))
    submitted = Column(Boolean)
    passed = Column(Boolean)
    grade = Column(String(255))
    commit_count = Column(Integer)
    raw_json = Column(Text)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    teacher = relationship('User', back_populates='classroom_records')

# Database setup
engine = create_engine(Config.get_database_url(), echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)
    try:
        _migrate_user_notification_columns()
        _migrate_user_role_column()
        _migrate_assignment_classroom_columns()
    except Exception as e:
        # Non-fatal: log and continue
        print(f"Migration check failed: {e}")

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AppSettings(Base):
    """Global application settings for notifications."""
    __tablename__ = 'app_settings'

    id = Column(Integer, primary_key=True)
    notify_threshold_hours = Column(Integer, default=Config.DEADLINE_WARNING_HOURS)
    notify_period_seconds = Column(Integer, default=Config.NOTIFICATION_CHECK_INTERVAL)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_or_create_settings(db: 'Session') -> 'AppSettings':
    settings = db.query(AppSettings).get(1)
    if not settings:
        settings = AppSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

def _migrate_user_notification_columns():
    """Ensure new user notification columns exist (best-effort, idempotent)."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == 'postgresql':
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_threshold_hours INTEGER"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_period_seconds INTEGER"))
        elif dialect == 'sqlite':
            # Check existing columns
            res = conn.execute(text("PRAGMA table_info('users')"))
            cols = {row[1] for row in res.fetchall()}
            if 'notify_threshold_hours' not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN notify_threshold_hours INTEGER"))
            if 'notify_period_seconds' not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN notify_period_seconds INTEGER"))
        else:
            # Attempt generic approach
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN notify_threshold_hours INTEGER"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN notify_period_seconds INTEGER"))
            except Exception:
                pass

def _migrate_user_role_column():
    """Ensure the user role column exists."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == 'postgresql':
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student' NOT NULL"))
        elif dialect == 'sqlite':
            res = conn.execute(text("PRAGMA table_info('users')"))
            cols = {row[1] for row in res.fetchall()}
            if 'role' not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'student' NOT NULL"))
        else:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'student' NOT NULL"))
            except Exception:
                pass

def _migrate_assignment_classroom_columns():
    """Ensure assignment classroom-related columns exist."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == 'postgresql':
            conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS classroom_assignment_id VARCHAR(255)"))
        elif dialect == 'sqlite':
            res = conn.execute(text("PRAGMA table_info('assignments')"))
            cols = {row[1] for row in res.fetchall()}
            if 'classroom_assignment_id' not in cols:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN classroom_assignment_id VARCHAR(255)"))
        else:
            try:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN classroom_assignment_id VARCHAR(255)"))
            except Exception:
                pass
