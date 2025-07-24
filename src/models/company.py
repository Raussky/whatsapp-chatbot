from datetime import datetime
from . import db
import uuid

class Company(db.Model):
    __tablename__ = 'companies'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    website = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100), default='Kazakhstan')
    timezone = db.Column(db.String(50), default='Asia/Almaty')
    logo_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    owner_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)
    
    # Relationships will be defined after all models are loaded
    # chatbots = db.relationship('Chatbot', backref='company', lazy=True, 
    #                           cascade='all, delete-orphan')
    # subscriptions = db.relationship('Subscription', backref='company', lazy=True,
    #                                cascade='all, delete-orphan')
    # analytics_events = db.relationship('AnalyticsEvent', backref='company', lazy=True,
    #                                   cascade='all, delete-orphan')
    
    def __init__(self, name, business_type, owner_id, **kwargs):
        self.name = name
        self.business_type = business_type
        self.owner_id = owner_id
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self, include_relationships=False):
        """Convert company object to dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'business_type': self.business_type,
            'description': self.description,
            'website': self.website,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'timezone': self.timezone,
            'logo_url': self.logo_url,
            'is_active': self.is_active,
            'owner_id': self.owner_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_relationships:
            # Include chatbot count
            active_chatbots = [cb for cb in self.chatbots if not cb.deleted_at]
            data['chatbot_count'] = len(active_chatbots)
            
            # Include current subscription
            current_subscription = self.get_current_subscription()
            if current_subscription:
                data['subscription'] = current_subscription.to_dict()
            else:
                data['subscription'] = None
            
            # Include team member count
            data['team_member_count'] = len(self.user_memberships) + 1  # +1 for owner
        
        return data
    
    def get_current_subscription(self):
        """Get the current active subscription"""
        return Subscription.query.filter_by(
            company_id=self.id,
            status='active'
        ).first()
    
    def get_active_chatbots(self):
        """Get all active chatbots for this company"""
        return [cb for cb in self.chatbots if not cb.deleted_at and cb.status == 'active']
    
    def get_team_members(self):
        """Get all team members including owner"""
        from .user import User, CompanyUser
        
        members = []
        
        # Add owner
        owner = User.query.get(self.owner_id)
        if owner:
            members.append({
                'user': owner,
                'role': 'owner',
                'permissions': {},
                'joined_at': self.created_at
            })
        
        # Add other members
        for membership in self.user_memberships:
            members.append({
                'user': membership.user,
                'role': membership.role,
                'permissions': membership.permissions or {},
                'joined_at': membership.joined_at
            })
        
        return members
    
    def can_create_chatbot(self):
        """Check if company can create more chatbots based on subscription"""
        subscription = self.get_current_subscription()
        if not subscription:
            return False
        
        plan = subscription.plan
        if plan.max_chatbots == -1:  # Unlimited
            return True
        
        active_chatbots_count = len(self.get_active_chatbots())
        return active_chatbots_count < plan.max_chatbots
    
    def get_usage_stats(self, period_start=None, period_end=None):
        """Get usage statistics for the company"""
        from .conversation import Conversation, Message
        from .analytics import AnalyticsEvent
        
        # Default to current month if no period specified
        if not period_start:
            from datetime import datetime, date
            today = date.today()
            period_start = datetime(today.year, today.month, 1)
        
        if not period_end:
            period_end = datetime.utcnow()
        
        # Count conversations
        conversation_count = db.session.query(Conversation).join(Chatbot).filter(
            Chatbot.company_id == self.id,
            Conversation.started_at >= period_start,
            Conversation.started_at <= period_end
        ).count()
        
        # Count messages
        message_count = db.session.query(Message).join(Conversation).join(Chatbot).filter(
            Chatbot.company_id == self.id,
            Message.created_at >= period_start,
            Message.created_at <= period_end
        ).count()
        
        # Count analytics events
        event_count = AnalyticsEvent.query.filter(
            AnalyticsEvent.company_id == self.id,
            AnalyticsEvent.created_at >= period_start,
            AnalyticsEvent.created_at <= period_end
        ).count()
        
        return {
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'conversation_count': conversation_count,
            'message_count': message_count,
            'event_count': event_count,
            'chatbot_count': len(self.get_active_chatbots())
        }
    
    def soft_delete(self):
        """Soft delete the company"""
        self.deleted_at = datetime.utcnow()
        self.is_active = False
        
        # Soft delete all chatbots
        for chatbot in self.chatbots:
            if not chatbot.deleted_at:
                chatbot.soft_delete()
    
    @staticmethod
    def find_by_id(company_id):
        """Find company by ID (excluding deleted)"""
        return Company.query.filter_by(id=company_id, deleted_at=None).first()
    
    @staticmethod
    def find_by_owner(owner_id):
        """Find companies owned by a specific user"""
        return Company.query.filter_by(owner_id=owner_id, deleted_at=None).all()
    
    def __repr__(self):
        return f'<Company {self.name}>'


# Imports moved to __init__.py to avoid circular dependencies

