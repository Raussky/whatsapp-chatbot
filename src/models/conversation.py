from datetime import datetime
from . import db
import uuid

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = db.Column(db.String(36), db.ForeignKey('chatbots.id'), nullable=False)
    whatsapp_conversation_id = db.Column(db.String(255))
    customer_phone = db.Column(db.String(50), nullable=False)
    customer_name = db.Column(db.String(255))
    customer_profile_url = db.Column(db.String(500))
    status = db.Column(db.Enum('open', 'closed', 'archived', name='conversation_status'), 
                      nullable=False, default='open')
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    last_message_at = db.Column(db.DateTime)
    message_count = db.Column(db.Integer, nullable=False, default=0)
    tags = db.Column(db.JSON, default=[])
    conversation_metadata = db.Column(db.JSON, default={})
    assigned_to = db.Column(db.String(36), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy=True,
                              cascade='all, delete-orphan', order_by='Message.timestamp')
    assigned_user = db.relationship('User', foreign_keys=[assigned_to])
    
    def __init__(self, chatbot_id, customer_phone, **kwargs):
        self.chatbot_id = chatbot_id
        self.customer_phone = customer_phone
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self, include_messages=False):
        """Convert conversation to dictionary"""
        data = {
            'id': self.id,
            'chatbot_id': self.chatbot_id,
            'whatsapp_conversation_id': self.whatsapp_conversation_id,
            'customer_phone': self.customer_phone,
            'customer_name': self.customer_name,
            'customer_profile_url': self.customer_profile_url,
            'status': self.status,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'message_count': self.message_count,
            'tags': self.tags or [],
            'conversation_metadata': self.conversation_metadata or {},
            'assigned_to': self.assigned_to,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_messages:
            data['messages'] = [msg.to_dict() for msg in self.messages]
        
        if self.assigned_user:
            data['assigned_user'] = {
                'id': self.assigned_user.id,
                'name': self.assigned_user.get_full_name(),
                'email': self.assigned_user.email
            }
        
        return data
    
    def add_message(self, message_data):
        """Add a new message to the conversation"""
        message = Message(
            conversation_id=self.id,
            **message_data
        )
        
        db.session.add(message)
        
        # Update conversation metadata
        self.message_count += 1
        self.last_message_at = message.timestamp
        self.updated_at = datetime.utcnow()
        
        return message
    
    def close(self):
        """Close the conversation"""
        self.status = 'closed'
        self.ended_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def reopen(self):
        """Reopen a closed conversation"""
        self.status = 'open'
        self.ended_at = None
        self.updated_at = datetime.utcnow()
    
    def archive(self):
        """Archive the conversation"""
        self.status = 'archived'
        self.updated_at = datetime.utcnow()
    
    def assign_to_user(self, user_id):
        """Assign conversation to a user"""
        self.assigned_to = user_id
        self.updated_at = datetime.utcnow()
    
    def add_tag(self, tag):
        """Add a tag to the conversation"""
        if not self.tags:
            self.tags = []
        
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.utcnow()
    
    def remove_tag(self, tag):
        """Remove a tag from the conversation"""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.utcnow()
    
    def update_metadata(self, new_metadata):
        """Update conversation metadata"""
        if self.conversation_metadata:
            self.conversation_metadata.update(new_metadata)
        else:
            self.conversation_metadata = new_metadata
        
        self.updated_at = datetime.utcnow()
    
    def get_duration_minutes(self):
        """Get conversation duration in minutes"""
        if not self.ended_at:
            end_time = datetime.utcnow()
        else:
            end_time = self.ended_at
        
        duration = end_time - self.started_at
        return duration.total_seconds() / 60
    
    def get_last_customer_message(self):
        """Get the last message from the customer"""
        return Message.query.filter_by(
            conversation_id=self.id,
            direction='inbound'
        ).order_by(Message.timestamp.desc()).first()
    
    def get_last_bot_message(self):
        """Get the last message from the bot"""
        return Message.query.filter_by(
            conversation_id=self.id,
            direction='outbound'
        ).order_by(Message.timestamp.desc()).first()
    
    @staticmethod
    def find_by_customer_phone(chatbot_id, customer_phone):
        """Find conversation by customer phone number"""
        return Conversation.query.filter_by(
            chatbot_id=chatbot_id,
            customer_phone=customer_phone,
            status='open'
        ).first()
    
    @staticmethod
    def find_active_conversations(chatbot_id):
        """Find all active conversations for a chatbot"""
        return Conversation.query.filter_by(
            chatbot_id=chatbot_id,
            status='open'
        ).order_by(Conversation.last_message_at.desc()).all()
    
    def __repr__(self):
        return f'<Conversation {self.id} - {self.customer_phone}>'


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id'), nullable=False)
    whatsapp_message_id = db.Column(db.String(255))
    direction = db.Column(db.Enum('inbound', 'outbound', name='message_direction'), nullable=False)
    type = db.Column(db.Enum('text', 'image', 'audio', 'video', 'document', 'location', 'contact', 'interactive', 
                            name='message_type'), nullable=False, default='text')
    content = db.Column(db.Text)
    media_url = db.Column(db.String(500))
    media_type = db.Column(db.String(100))
    media_size = db.Column(db.Integer)
    sender_phone = db.Column(db.String(50))
    sender_name = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    delivered_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    message_metadata = db.Column(db.JSON, default={})
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __init__(self, conversation_id, direction, type='text', **kwargs):
        self.conversation_id = conversation_id
        self.direction = direction
        self.type = type
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        """Convert message to dictionary"""
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'whatsapp_message_id': self.whatsapp_message_id,
            'direction': self.direction,
            'type': self.type,
            'content': self.content,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'media_size': self.media_size,
            'sender_phone': self.sender_phone,
            'sender_name': self.sender_name,
            'timestamp': self.timestamp.isoformat(),
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'error_message': self.error_message,
            'message_metadata': self.message_metadata or {},
            'created_at': self.created_at.isoformat()
        }
    
    def mark_delivered(self):
        """Mark message as delivered"""
        self.delivered_at = datetime.utcnow()
    
    def mark_read(self):
        """Mark message as read"""
        self.read_at = datetime.utcnow()
    
    def mark_failed(self, error_message):
        """Mark message as failed"""
        self.failed_at = datetime.utcnow()
        self.error_message = error_message
    
    def is_from_customer(self):
        """Check if message is from customer"""
        return self.direction == 'inbound'
    
    def is_from_bot(self):
        """Check if message is from bot"""
        return self.direction == 'outbound'
    
    def has_media(self):
        """Check if message contains media"""
        return self.type in ['image', 'audio', 'video', 'document'] and self.media_url
    
    def get_display_content(self):
        """Get display-friendly content"""
        if self.type == 'text':
            return self.content
        elif self.has_media():
            return f"[{self.type.upper()}] {self.content or 'Media file'}"
        elif self.type == 'location':
            return "[LOCATION] Location shared"
        elif self.type == 'contact':
            return "[CONTACT] Contact shared"
        elif self.type == 'interactive':
            return f"[INTERACTIVE] {self.content or 'Interactive message'}"
        else:
            return self.content or f"[{self.type.upper()}] Message"
    
    @staticmethod
    def find_by_whatsapp_id(whatsapp_message_id):
        """Find message by WhatsApp message ID"""
        return Message.query.filter_by(whatsapp_message_id=whatsapp_message_id).first()
    
    @staticmethod
    def get_conversation_messages(conversation_id, limit=50, offset=0):
        """Get messages for a conversation with pagination"""
        return Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.desc()).offset(offset).limit(limit).all()
    
    def __repr__(self):
        return f'<Message {self.id} - {self.type} - {self.direction}>'

