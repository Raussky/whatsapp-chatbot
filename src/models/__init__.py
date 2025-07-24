from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy
db = SQLAlchemy()

# Import all models to ensure they are registered with SQLAlchemy
from .user import User, CompanyUser
from .company import Company
from .subscription import Subscription, SubscriptionPlan
from .chatbot import Chatbot
from .conversation import Conversation, Message
from .analytics import AnalyticsEvent
from .webhook import WebhookEvent
from .invoice import Invoice, UsageTracking

__all__ = [
    'db',
    'User',
    'CompanyUser', 
    'Company',
    'Subscription',
    'SubscriptionPlan',
    'Chatbot',
    'Conversation',
    'Message',
    'AnalyticsEvent',
    'WebhookEvent',
    'Invoice',
    'UsageTracking'
]

