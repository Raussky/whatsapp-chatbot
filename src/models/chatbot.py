from datetime import datetime
from . import db
import uuid
import json

class Chatbot(db.Model):
    __tablename__ = 'chatbots'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    botpress_bot_id = db.Column(db.String(255), unique=True)
    whatsapp_phone_number = db.Column(db.String(50))
    whatsapp_phone_number_id = db.Column(db.String(255))
    whatsapp_business_account_id = db.Column(db.String(255))
    status = db.Column(db.Enum('draft', 'active', 'inactive', 'error', name='chatbot_status'), 
                      nullable=False, default='draft')
    configuration = db.Column(db.JSON, default={})
    welcome_message = db.Column(db.Text)
    fallback_message = db.Column(db.Text)
    business_hours = db.Column(db.JSON, default={})
    auto_response_enabled = db.Column(db.Boolean, nullable=False, default=True)
    human_handoff_enabled = db.Column(db.Boolean, nullable=False, default=False)
    analytics_enabled = db.Column(db.Boolean, nullable=False, default=True)
    webhook_url = db.Column(db.String(500))
    webhook_secret = db.Column(db.String(255))
    last_deployed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='chatbot', lazy=True,
                                   cascade='all, delete-orphan')
    webhook_events = db.relationship('WebhookEvent', backref='chatbot', lazy=True,
                                    cascade='all, delete-orphan')
    analytics_events = db.relationship('AnalyticsEvent', backref='chatbot', lazy=True,
                                      cascade='all, delete-orphan')
    
    def __init__(self, company_id, name, **kwargs):
        self.company_id = company_id
        self.name = name
        
        # Set default configuration
        self.configuration = {
            'language': 'en',
            'timezone': 'Asia/Almaty',
            'max_conversation_length': 100,
            'session_timeout_minutes': 30,
            'enable_typing_indicator': True,
            'enable_read_receipts': True
        }
        
        # Set default business hours (9 AM to 6 PM, Monday to Friday)
        self.business_hours = {
            'enabled': False,
            'timezone': 'Asia/Almaty',
            'schedule': {
                'monday': {'start': '09:00', 'end': '18:00', 'enabled': True},
                'tuesday': {'start': '09:00', 'end': '18:00', 'enabled': True},
                'wednesday': {'start': '09:00', 'end': '18:00', 'enabled': True},
                'thursday': {'start': '09:00', 'end': '18:00', 'enabled': True},
                'friday': {'start': '09:00', 'end': '18:00', 'enabled': True},
                'saturday': {'start': '09:00', 'end': '18:00', 'enabled': False},
                'sunday': {'start': '09:00', 'end': '18:00', 'enabled': False}
            },
            'out_of_hours_message': 'Thank you for your message. Our business hours are Monday to Friday, 9 AM to 6 PM. We will respond to your message during business hours.'
        }
        
        # Set default messages
        self.welcome_message = 'Hello! Welcome to our WhatsApp chatbot. How can I help you today?'
        self.fallback_message = 'I\'m sorry, I didn\'t understand that. Could you please rephrase your question or type "help" for assistance?'
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self, include_stats=False):
        """Convert chatbot to dictionary"""
        data = {
            'id': self.id,
            'company_id': self.company_id,
            'name': self.name,
            'description': self.description,
            'botpress_bot_id': self.botpress_bot_id,
            'whatsapp_phone_number': self.whatsapp_phone_number,
            'whatsapp_phone_number_id': self.whatsapp_phone_number_id,
            'whatsapp_business_account_id': self.whatsapp_business_account_id,
            'status': self.status,
            'configuration': self.configuration or {},
            'welcome_message': self.welcome_message,
            'fallback_message': self.fallback_message,
            'business_hours': self.business_hours or {},
            'auto_response_enabled': self.auto_response_enabled,
            'human_handoff_enabled': self.human_handoff_enabled,
            'analytics_enabled': self.analytics_enabled,
            'webhook_url': self.webhook_url,
            'last_deployed_at': self.last_deployed_at.isoformat() if self.last_deployed_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_stats:
            stats = self.get_stats()
            data.update(stats)
        
        return data
    
    def get_stats(self, days=30):
        """Get chatbot statistics for the specified number of days"""
        from datetime import timedelta
        from .conversation import Conversation, Message
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Count conversations
        total_conversations = Conversation.query.filter(
            Conversation.chatbot_id == self.id,
            Conversation.started_at >= cutoff_date
        ).count()
        
        # Count messages
        total_messages = db.session.query(Message).join(Conversation).filter(
            Conversation.chatbot_id == self.id,
            Message.created_at >= cutoff_date
        ).count()
        
        # Count active conversations
        active_conversations = Conversation.query.filter(
            Conversation.chatbot_id == self.id,
            Conversation.status == 'open'
        ).count()
        
        # Calculate average response time (placeholder - would need more complex query)
        avg_response_time_minutes = 5  # Placeholder
        
        return {
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'active_conversations': active_conversations,
            'avg_response_time_minutes': avg_response_time_minutes,
            'stats_period_days': days
        }
    
    def is_within_business_hours(self):
        """Check if current time is within business hours"""
        if not self.business_hours.get('enabled', False):
            return True  # Always available if business hours not enabled
        
        from datetime import datetime
        import pytz
        
        try:
            # Get timezone
            tz_name = self.business_hours.get('timezone', 'Asia/Almaty')
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
            
            # Get current day of week (monday=0, sunday=6)
            weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            current_day = weekday_names[now.weekday()]
            
            # Check if day is enabled
            day_schedule = self.business_hours.get('schedule', {}).get(current_day, {})
            if not day_schedule.get('enabled', False):
                return False
            
            # Check time range
            start_time = day_schedule.get('start', '09:00')
            end_time = day_schedule.get('end', '18:00')
            
            current_time = now.strftime('%H:%M')
            
            return start_time <= current_time <= end_time
            
        except Exception:
            # If any error occurs, default to available
            return True
    
    def update_configuration(self, new_config):
        """Update chatbot configuration"""
        if self.configuration:
            self.configuration.update(new_config)
        else:
            self.configuration = new_config
        
        # Mark as updated
        self.updated_at = datetime.utcnow()
    
    def deploy(self):
        """Mark chatbot as deployed"""
        self.status = 'active'
        self.last_deployed_at = datetime.utcnow()
    
    def deactivate(self):
        """Deactivate the chatbot"""
        self.status = 'inactive'
    
    def soft_delete(self):
        """Soft delete the chatbot"""
        self.deleted_at = datetime.utcnow()
        self.status = 'inactive'
    
    def can_send_message(self):
        """Check if chatbot can send messages"""
        return (
            self.status == 'active' and
            self.whatsapp_phone_number and
            self.botpress_bot_id and
            not self.deleted_at
        )
    
    def get_webhook_url(self):
        """Get the webhook URL for this chatbot"""
        if self.webhook_url:
            return self.webhook_url
        
        # Generate default webhook URL
        from flask import current_app
        base_url = current_app.config.get('BACKEND_URL', 'http://localhost:5000')
        return f"{base_url}/api/webhooks/whatsapp/{self.id}"
    
    def validate_whatsapp_setup(self):
        """Validate WhatsApp setup for this chatbot"""
        errors = []
        
        if not self.whatsapp_phone_number:
            errors.append('WhatsApp phone number is required')
        
        if not self.whatsapp_phone_number_id:
            errors.append('WhatsApp phone number ID is required')
        
        if not self.whatsapp_business_account_id:
            errors.append('WhatsApp Business Account ID is required')
        
        return errors
    
    def validate_botpress_setup(self):
        """Validate Botpress setup for this chatbot"""
        errors = []
        
        if not self.botpress_bot_id:
            errors.append('Botpress bot ID is required')
        
        return errors
    
    @staticmethod
    def find_by_id(chatbot_id):
        """Find chatbot by ID (excluding deleted)"""
        return Chatbot.query.filter_by(id=chatbot_id, deleted_at=None).first()
    
    @staticmethod
    def find_by_company(company_id):
        """Find all chatbots for a company (excluding deleted)"""
        return Chatbot.query.filter_by(company_id=company_id, deleted_at=None).all()
    
    @staticmethod
    def find_by_botpress_id(botpress_bot_id):
        """Find chatbot by Botpress bot ID"""
        return Chatbot.query.filter_by(botpress_bot_id=botpress_bot_id, deleted_at=None).first()
    
    @staticmethod
    def find_by_whatsapp_number(phone_number):
        """Find chatbot by WhatsApp phone number"""
        return Chatbot.query.filter_by(whatsapp_phone_number=phone_number, deleted_at=None).first()
    
    def __repr__(self):
        return f'<Chatbot {self.name}>'

