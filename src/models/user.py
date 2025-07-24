from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

from . import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('admin', 'company_owner', 'company_user', name='user_role'), 
                     nullable=False, default='company_user')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_token = db.Column(db.String(255))
    reset_password_token = db.Column(db.String(255))
    reset_password_expires = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)
    
    # Relationships will be defined after all models are loaded
    # owned_companies = db.relationship('Company', backref='owner', lazy=True, foreign_keys='Company.owner_id')
    # company_memberships = db.relationship('CompanyUser', backref='user', lazy=True)
    
    def __init__(self, email, password, first_name, last_name, role='company_user'):
        self.email = email
        self.set_password(password)
        self.first_name = first_name
        self.last_name = last_name
        self.role = role
    
    def set_password(self, password):
        """Hash and set the user's password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the provided password matches the user's password"""
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        """Get the user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self, include_sensitive=False):
        """Convert user object to dictionary"""
        data = {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.get_full_name(),
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_sensitive:
            data.update({
                'verification_token': self.verification_token,
                'reset_password_token': self.reset_password_token,
                'reset_password_expires': self.reset_password_expires.isoformat() if self.reset_password_expires else None
            })
        
        return data
    
    def has_permission(self, permission, company_id=None):
        """Check if user has a specific permission"""
        if self.role == 'admin':
            return True
        
        if company_id:
            # Check company-specific permissions
            membership = CompanyUser.query.filter_by(
                user_id=self.id, 
                company_id=company_id
            ).first()
            
            if membership:
                permissions = membership.permissions or {}
                return permissions.get(permission, False)
        
        return False
    
    def get_companies(self):
        """Get all companies the user has access to"""
        companies = []
        
        # Add owned companies
        for company in self.owned_companies:
            if not company.deleted_at:
                companies.append({
                    'company': company,
                    'role': 'owner',
                    'permissions': {}
                })
        
        # Add member companies
        for membership in self.company_memberships:
            if not membership.company.deleted_at:
                companies.append({
                    'company': membership.company,
                    'role': membership.role,
                    'permissions': membership.permissions or {}
                })
        
        return companies
    
    @staticmethod
    def find_by_email(email):
        """Find user by email address"""
        return User.query.filter_by(email=email, deleted_at=None).first()
    
    @staticmethod
    def find_by_id(user_id):
        """Find user by ID"""
        return User.query.filter_by(id=user_id, deleted_at=None).first()
    
    def __repr__(self):
        return f'<User {self.email}>'


class CompanyUser(db.Model):
    """Junction table for company-user relationships"""
    __tablename__ = 'company_users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='member')
    permissions = db.Column(db.JSON, default={})
    invited_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    invited_at = db.Column(db.DateTime)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    company = db.relationship('Company', backref='user_memberships')
    inviter = db.relationship('User', foreign_keys=[invited_by])
    
    __table_args__ = (db.UniqueConstraint('company_id', 'user_id'),)
    
    def to_dict(self):
        """Convert company user relationship to dictionary"""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'user_id': self.user_id,
            'role': self.role,
            'permissions': self.permissions,
            'invited_by': self.invited_by,
            'invited_at': self.invited_at.isoformat() if self.invited_at else None,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'created_at': self.created_at.isoformat()
        }

