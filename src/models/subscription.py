from datetime import datetime, timedelta
from . import db
import uuid

class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    plan_type = db.Column(db.Enum('starter', 'business', 'enterprise', name='subscription_plan'), 
                         nullable=False)
    description = db.Column(db.Text)
    price_monthly = db.Column(db.Numeric(10, 2), nullable=False)
    price_yearly = db.Column(db.Numeric(10, 2))
    max_chatbots = db.Column(db.Integer, nullable=False, default=1)
    max_conversations_per_month = db.Column(db.Integer, nullable=False, default=1000)
    max_messages_per_month = db.Column(db.Integer, nullable=False, default=10000)
    features = db.Column(db.JSON, default={})
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='plan', lazy=True)
    
    def __init__(self, name, plan_type, price_monthly, **kwargs):
        self.name = name
        self.plan_type = plan_type
        self.price_monthly = price_monthly
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        """Convert subscription plan to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'plan_type': self.plan_type,
            'description': self.description,
            'price_monthly': float(self.price_monthly) if self.price_monthly else None,
            'price_yearly': float(self.price_yearly) if self.price_yearly else None,
            'max_chatbots': self.max_chatbots,
            'max_conversations_per_month': self.max_conversations_per_month,
            'max_messages_per_month': self.max_messages_per_month,
            'features': self.features or {},
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def get_yearly_discount_percentage(self):
        """Calculate yearly discount percentage"""
        if not self.price_yearly or not self.price_monthly:
            return 0
        
        monthly_yearly_total = float(self.price_monthly) * 12
        yearly_price = float(self.price_yearly)
        
        if monthly_yearly_total > 0:
            discount = ((monthly_yearly_total - yearly_price) / monthly_yearly_total) * 100
            return round(discount, 1)
        
        return 0
    
    @staticmethod
    def get_active_plans():
        """Get all active subscription plans"""
        return SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.price_monthly).all()
    
    @staticmethod
    def find_by_type(plan_type):
        """Find plan by type"""
        return SubscriptionPlan.query.filter_by(plan_type=plan_type, is_active=True).first()
    
    def __repr__(self):
        return f'<SubscriptionPlan {self.name}>'


class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    plan_id = db.Column(db.String(36), db.ForeignKey('subscription_plans.id'), nullable=False)
    status = db.Column(db.Enum('active', 'inactive', 'cancelled', 'past_due', 'trialing', 
                              name='subscription_status'), nullable=False, default='trialing')
    current_period_start = db.Column(db.DateTime, nullable=False)
    current_period_end = db.Column(db.DateTime, nullable=False)
    trial_end = db.Column(db.DateTime)
    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False)
    cancelled_at = db.Column(db.DateTime)
    stripe_subscription_id = db.Column(db.String(255))
    stripe_customer_id = db.Column(db.String(255))
    payment_method_id = db.Column(db.String(255))
    last_payment_date = db.Column(db.DateTime)
    next_payment_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoices = db.relationship('Invoice', backref='subscription', lazy=True,
                              cascade='all, delete-orphan')
    usage_tracking = db.relationship('UsageTracking', backref='subscription', lazy=True,
                                    cascade='all, delete-orphan')
    
    def __init__(self, company_id, plan_id, **kwargs):
        self.company_id = company_id
        self.plan_id = plan_id
        
        # Set default period (30 days from now)
        now = datetime.utcnow()
        self.current_period_start = now
        self.current_period_end = now + timedelta(days=30)
        
        # Set trial end (7 days from now)
        self.trial_end = now + timedelta(days=7)
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self, include_plan=True):
        """Convert subscription to dictionary"""
        data = {
            'id': self.id,
            'company_id': self.company_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'current_period_start': self.current_period_start.isoformat(),
            'current_period_end': self.current_period_end.isoformat(),
            'trial_end': self.trial_end.isoformat() if self.trial_end else None,
            'cancel_at_period_end': self.cancel_at_period_end,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'stripe_subscription_id': self.stripe_subscription_id,
            'stripe_customer_id': self.stripe_customer_id,
            'payment_method_id': self.payment_method_id,
            'last_payment_date': self.last_payment_date.isoformat() if self.last_payment_date else None,
            'next_payment_date': self.next_payment_date.isoformat() if self.next_payment_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_plan and self.plan:
            data['plan'] = self.plan.to_dict()
        
        return data
    
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status in ['active', 'trialing']
    
    def is_trial(self):
        """Check if subscription is in trial period"""
        if not self.trial_end:
            return False
        return datetime.utcnow() < self.trial_end and self.status == 'trialing'
    
    def days_until_renewal(self):
        """Get days until next renewal"""
        if not self.current_period_end:
            return 0
        
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)
    
    def days_remaining_in_trial(self):
        """Get days remaining in trial"""
        if not self.is_trial():
            return 0
        
        delta = self.trial_end - datetime.utcnow()
        return max(0, delta.days)
    
    def can_use_feature(self, feature_name):
        """Check if subscription allows usage of a specific feature"""
        if not self.is_active():
            return False
        
        features = self.plan.features or {}
        return features.get(feature_name, False)
    
    def get_usage_limits(self):
        """Get current usage limits based on plan"""
        return {
            'max_chatbots': self.plan.max_chatbots,
            'max_conversations_per_month': self.plan.max_conversations_per_month,
            'max_messages_per_month': self.plan.max_messages_per_month
        }
    
    def get_current_usage(self):
        """Get current usage for this billing period"""
        from .chatbot import Chatbot
        from .conversation import Message, Conversation
        from .company import CompanyUser
        
        # Calculate usage from existing data
        chatbots_count = Chatbot.query.filter_by(company_id=self.company_id).count()
        
        # Count messages in current billing period
        messages_count = Message.query.join(Conversation).join(Chatbot).filter(
            Chatbot.company_id == self.company_id,
            Message.created_at >= self.current_period_start,
            Message.created_at <= self.current_period_end
        ).count()
        
        # Count users
        users_count = CompanyUser.query.filter_by(company_id=self.company_id).count()
        
        return {
            'chatbots': chatbots_count,
            'messages': messages_count,
            'users': users_count,
            'storage_gb': 0  # Placeholder for storage calculation
        }
    
    def cancel(self, at_period_end=True):
        """Cancel the subscription"""
        if at_period_end:
            self.cancel_at_period_end = True
        else:
            self.status = 'cancelled'
            self.cancelled_at = datetime.utcnow()
    
    def reactivate(self):
        """Reactivate a cancelled subscription"""
        if self.status == 'cancelled':
            self.status = 'active'
            self.cancelled_at = None
            self.cancel_at_period_end = False
    
    def renew(self, new_period_end=None):
        """Renew the subscription for another period"""
        if not new_period_end:
            # Default to 30 days from current period end
            new_period_end = self.current_period_end + timedelta(days=30)
        
        self.current_period_start = self.current_period_end
        self.current_period_end = new_period_end
        self.last_payment_date = datetime.utcnow()
        self.next_payment_date = new_period_end
        
        if self.status in ['trialing', 'past_due']:
            self.status = 'active'
    
    @staticmethod
    def find_by_company(company_id):
        """Find active subscription for a company"""
        return Subscription.query.filter_by(
            company_id=company_id,
            status='active'
        ).first()
    
    @staticmethod
    def find_expiring_soon(days=7):
        """Find subscriptions expiring within specified days"""
        cutoff_date = datetime.utcnow() + timedelta(days=days)
        return Subscription.query.filter(
            Subscription.current_period_end <= cutoff_date,
            Subscription.status.in_(['active', 'trialing'])
        ).all()
    
    def __repr__(self):
        return f'<Subscription {self.id} - {self.status}>'


# Imports moved to __init__.py to avoid circular dependencies

