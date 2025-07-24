from datetime import datetime
from . import db
import uuid

class AnalyticsEvent(db.Model):
    __tablename__ = 'analytics_events'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    chatbot_id = db.Column(db.String(36), db.ForeignKey('chatbots.id'))
    event_name = db.Column(db.String(100), nullable=False)
    event_data = db.Column(db.JSON, default={})
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    session_id = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id])
    
    def __init__(self, company_id, event_name, **kwargs):
        self.company_id = company_id
        self.event_name = event_name
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        """Convert analytics event to dictionary"""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'chatbot_id': self.chatbot_id,
            'event_name': self.event_name,
            'event_data': self.event_data or {},
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat()
        }
    
    @staticmethod
    def track_event(company_id, event_name, **kwargs):
        """Track an analytics event"""
        event = AnalyticsEvent(
            company_id=company_id,
            event_name=event_name,
            **kwargs
        )
        
        db.session.add(event)
        return event
    
    @staticmethod
    def get_events_by_company(company_id, start_date=None, end_date=None, event_name=None, limit=100):
        """Get analytics events for a company"""
        query = AnalyticsEvent.query.filter_by(company_id=company_id)
        
        if start_date:
            query = query.filter(AnalyticsEvent.created_at >= start_date)
        
        if end_date:
            query = query.filter(AnalyticsEvent.created_at <= end_date)
        
        if event_name:
            query = query.filter_by(event_name=event_name)
        
        return query.order_by(AnalyticsEvent.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_event_counts(company_id, start_date=None, end_date=None, group_by='event_name'):
        """Get event counts grouped by specified field"""
        from sqlalchemy import func
        
        query = db.session.query(
            getattr(AnalyticsEvent, group_by),
            func.count(AnalyticsEvent.id).label('count')
        ).filter_by(company_id=company_id)
        
        if start_date:
            query = query.filter(AnalyticsEvent.created_at >= start_date)
        
        if end_date:
            query = query.filter(AnalyticsEvent.created_at <= end_date)
        
        return query.group_by(getattr(AnalyticsEvent, group_by)).all()
    
    @staticmethod
    def get_daily_stats(company_id, days=30):
        """Get daily analytics statistics"""
        from sqlalchemy import func, text
        from datetime import timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get daily event counts
        daily_counts = db.session.query(
            func.date(AnalyticsEvent.created_at).label('date'),
            func.count(AnalyticsEvent.id).label('event_count')
        ).filter(
            AnalyticsEvent.company_id == company_id,
            AnalyticsEvent.created_at >= start_date
        ).group_by(func.date(AnalyticsEvent.created_at)).all()
        
        return [
            {
                'date': str(row.date),
                'event_count': row.event_count
            }
            for row in daily_counts
        ]
    
    def __repr__(self):
        return f'<AnalyticsEvent {self.event_name} - {self.company_id}>'


# Common analytics event types
class AnalyticsEventTypes:
    # User events
    USER_LOGIN = 'user_login'
    USER_LOGOUT = 'user_logout'
    USER_REGISTERED = 'user_registered'
    
    # Company events
    COMPANY_CREATED = 'company_created'
    COMPANY_UPDATED = 'company_updated'
    
    # Chatbot events
    CHATBOT_CREATED = 'chatbot_created'
    CHATBOT_DEPLOYED = 'chatbot_deployed'
    CHATBOT_DEACTIVATED = 'chatbot_deactivated'
    CHATBOT_DELETED = 'chatbot_deleted'
    
    # Conversation events
    CONVERSATION_STARTED = 'conversation_started'
    CONVERSATION_ENDED = 'conversation_ended'
    MESSAGE_SENT = 'message_sent'
    MESSAGE_RECEIVED = 'message_received'
    
    # Subscription events
    SUBSCRIPTION_CREATED = 'subscription_created'
    SUBSCRIPTION_UPGRADED = 'subscription_upgraded'
    SUBSCRIPTION_DOWNGRADED = 'subscription_downgraded'
    SUBSCRIPTION_CANCELLED = 'subscription_cancelled'
    PAYMENT_SUCCESSFUL = 'payment_successful'
    PAYMENT_FAILED = 'payment_failed'
    
    # Feature usage events
    FEATURE_USED = 'feature_used'
    API_CALL_MADE = 'api_call_made'
    WEBHOOK_RECEIVED = 'webhook_received'
    
    # Error events
    ERROR_OCCURRED = 'error_occurred'
    INTEGRATION_ERROR = 'integration_error'

