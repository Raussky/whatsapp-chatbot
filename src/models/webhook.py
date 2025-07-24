from datetime import datetime
from . import db
import uuid

class WebhookEvent(db.Model):
    __tablename__ = 'webhook_events'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = db.Column(db.String(36), db.ForeignKey('chatbots.id'))
    event_type = db.Column(db.Enum('message_received', 'message_sent', 'conversation_started', 
                                  'conversation_ended', 'bot_error', name='webhook_event_type'), 
                          nullable=False)
    source = db.Column(db.String(50), nullable=False)  # 'botpress', 'whatsapp', 'stripe'
    payload = db.Column(db.JSON, nullable=False)
    processed = db.Column(db.Boolean, nullable=False, default=False)
    processed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __init__(self, event_type, source, payload, **kwargs):
        self.event_type = event_type
        self.source = source
        self.payload = payload
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        """Convert webhook event to dictionary"""
        return {
            'id': self.id,
            'chatbot_id': self.chatbot_id,
            'event_type': self.event_type,
            'source': self.source,
            'payload': self.payload,
            'processed': self.processed,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat()
        }
    
    def mark_processed(self):
        """Mark webhook event as processed"""
        self.processed = True
        self.processed_at = datetime.utcnow()
    
    def mark_failed(self, error_message):
        """Mark webhook event as failed"""
        self.error_message = error_message
        self.retry_count += 1
    
    def can_retry(self, max_retries=3):
        """Check if webhook event can be retried"""
        return self.retry_count < max_retries and not self.processed
    
    @staticmethod
    def create_event(event_type, source, payload, chatbot_id=None):
        """Create a new webhook event"""
        event = WebhookEvent(
            event_type=event_type,
            source=source,
            payload=payload,
            chatbot_id=chatbot_id
        )
        
        db.session.add(event)
        return event
    
    @staticmethod
    def get_unprocessed_events(limit=100):
        """Get unprocessed webhook events"""
        return WebhookEvent.query.filter_by(
            processed=False
        ).order_by(WebhookEvent.created_at).limit(limit).all()
    
    @staticmethod
    def get_failed_events(max_retries=3):
        """Get failed webhook events that can be retried"""
        return WebhookEvent.query.filter(
            WebhookEvent.processed == False,
            WebhookEvent.retry_count < max_retries,
            WebhookEvent.error_message.isnot(None)
        ).order_by(WebhookEvent.created_at).all()
    
    @staticmethod
    def cleanup_old_events(days=30):
        """Clean up old processed webhook events"""
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        old_events = WebhookEvent.query.filter(
            WebhookEvent.processed == True,
            WebhookEvent.created_at < cutoff_date
        ).all()
        
        for event in old_events:
            db.session.delete(event)
        
        return len(old_events)
    
    def __repr__(self):
        return f'<WebhookEvent {self.event_type} - {self.source}>'


# Webhook event types
class WebhookEventTypes:
    MESSAGE_RECEIVED = 'message_received'
    MESSAGE_SENT = 'message_sent'
    CONVERSATION_STARTED = 'conversation_started'
    CONVERSATION_ENDED = 'conversation_ended'
    BOT_ERROR = 'bot_error'


# Webhook sources
class WebhookSources:
    BOTPRESS = 'botpress'
    WHATSAPP = 'whatsapp'
    STRIPE = 'stripe'

