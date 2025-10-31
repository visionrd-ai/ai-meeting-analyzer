"""
Database models for Perfect AI Meeting Analyzer
User authentication and data separation
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication and data separation."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    sessions = db.relationship('RecordingSession', backref='user', lazy=True, cascade='all, delete-orphan')
    recordings = db.relationship('Recording', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        """Return user ID for Flask-Login."""
        return str(self.id)
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class RecordingSession(db.Model):
    """Recording session model - each user's sessions are separate."""
    
    __tablename__ = 'recording_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Session details
    title = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, default=0)
    
    # Recording settings
    audio_source = db.Column(db.String(20), default='mic')  # mic, system, both
    transcription_engine = db.Column(db.String(30), default='faster_whisper')
    analysis_mode = db.Column(db.String(20), default='automatic')
    word_threshold = db.Column(db.Integer, default=200)
    
    # Analysis results
    transcript_text = db.Column(db.Text, nullable=True)
    transcript_segments = db.Column(db.Text, nullable=True)  # JSON array of segments
    current_analysis = db.Column(db.Text, nullable=True)     # JSON
    final_analysis = db.Column(db.Text, nullable=True)       # JSON
    
    # Analysis metadata
    analysis_generated_at = db.Column(db.DateTime, nullable=True)
    analysis_word_count = db.Column(db.Integer, default=0)
    analysis_confidence = db.Column(db.Float, nullable=True)
    
    # Statistics
    total_words = db.Column(db.Integer, default=0)
    total_segments = db.Column(db.Integer, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    recordings = db.relationship('Recording', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self, include_content=False):
        """Convert session to dictionary."""
        data = {
            'id': self.id,
            'session_id': self.session_id,
            'title': self.title,
            'description': self.description,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'duration_seconds': self.duration_seconds,
            'duration_formatted': f"{self.duration_seconds // 60:02d}:{self.duration_seconds % 60:02d}" if self.duration_seconds else "00:00",
            'audio_source': self.audio_source,
            'transcription_engine': self.transcription_engine,
            'analysis_mode': self.analysis_mode,
            'word_threshold': self.word_threshold,
            'total_words': self.total_words,
            'total_segments': self.total_segments,
            'analysis_generated_at': self.analysis_generated_at.isoformat() if self.analysis_generated_at else None,
            'analysis_word_count': self.analysis_word_count,
            'analysis_confidence': self.analysis_confidence,
            'is_active': self.is_active,
            'has_transcript': bool(self.transcript_text),
            'has_analysis': bool(self.final_analysis),
            'recording_count': len(self.recordings) if self.recordings else 0
        }
        
        if include_content:
            import json
            data.update({
                'transcript_text': self.transcript_text,
                'transcript_segments': json.loads(self.transcript_segments) if self.transcript_segments else [],
                'current_analysis': json.loads(self.current_analysis) if self.current_analysis else None,
                'final_analysis': json.loads(self.final_analysis) if self.final_analysis else None
            })
        
        return data

class Recording(db.Model):
    """Individual recording files - each user's recordings are separate."""
    
    __tablename__ = 'recordings'
    
    id = db.Column(db.Integer, primary_key=True)
    recording_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('recording_sessions.id'), nullable=True)
    
    # File details
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=False)
    file_size_bytes = db.Column(db.BigInteger, nullable=False)
    duration_seconds = db.Column(db.Float, nullable=True)
    
    # Audio properties
    sample_rate = db.Column(db.Integer, default=16000)
    channels = db.Column(db.Integer, default=1)
    format = db.Column(db.String(10), default='wav')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    title = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated
    
    def to_dict(self):
        """Convert recording to dictionary."""
        return {
            'id': self.id,
            'recording_id': self.recording_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size_bytes': self.file_size_bytes,
            'file_size_mb': round(self.file_size_bytes / 1024 / 1024, 2) if self.file_size_bytes else 0,
            'duration_seconds': self.duration_seconds,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'format': self.format,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'title': self.title,
            'description': self.description,
            'tags': self.tags.split(',') if self.tags else []
        }

def init_db(app):
    """Initialize database with app."""
    db.init_app(app)
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Create default admin user if it doesn't exist
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@perfectai.com',
                full_name='Perfect AI Administrator'
            )
            admin_user.set_password('admin123')  # Change this in production!
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Default admin user created (username: admin, password: admin123)")