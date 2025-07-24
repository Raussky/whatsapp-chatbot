from datetime import datetime, date
from . import db
import uuid

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    subscription_id = db.Column(db.String(36), db.ForeignKey('subscriptions.id'), nullable=False)
    invoice_number = db.Column(db.String(100), nullable=False, unique=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='USD')
    status = db.Column(db.String(50), nullable=False, default='pending')
    due_date = db.Column(db.Date, nullable=False)
    paid_at = db.Column(db.DateTime)
    stripe_invoice_id = db.Column(db.String(255))
    pdf_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = db.relationship('Company', backref='invoices')
    
    def __init__(self, company_id, subscription_id, amount, **kwargs):
        self.company_id = company_id
        self.subscription_id = subscription_id
        self.amount = amount
        
        # Calculate total amount including tax
        tax_amount = kwargs.get('tax_amount', 0)
        self.tax_amount = tax_amount
        self.total_amount = amount + tax_amount
        
        # Generate invoice number
        self.invoice_number = self.generate_invoice_number()
        
        # Set due date (default 30 days from now)
        from datetime import timedelta
        self.due_date = (datetime.utcnow() + timedelta(days=30)).date()
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key) and key not in ['amount', 'tax_amount']:
                setattr(self, key, value)
    
    def to_dict(self):
        """Convert invoice to dictionary"""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'subscription_id': self.subscription_id,
            'invoice_number': self.invoice_number,
            'amount': float(self.amount),
            'tax_amount': float(self.tax_amount),
            'total_amount': float(self.total_amount),
            'currency': self.currency,
            'status': self.status,
            'due_date': self.due_date.isoformat(),
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'stripe_invoice_id': self.stripe_invoice_id,
            'pdf_url': self.pdf_url,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def generate_invoice_number(self):
        """Generate a unique invoice number"""
        from datetime import datetime
        
        # Format: INV-YYYY-MM-XXXXXX
        now = datetime.utcnow()
        prefix = f"INV-{now.year:04d}-{now.month:02d}"
        
        # Find the highest invoice number for this month
        latest_invoice = Invoice.query.filter(
            Invoice.invoice_number.like(f"{prefix}-%")
        ).order_by(Invoice.invoice_number.desc()).first()
        
        if latest_invoice:
            # Extract the sequence number and increment
            try:
                last_sequence = int(latest_invoice.invoice_number.split('-')[-1])
                sequence = last_sequence + 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            sequence = 1
        
        return f"{prefix}-{sequence:06d}"
    
    def mark_paid(self):
        """Mark invoice as paid"""
        self.status = 'paid'
        self.paid_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_failed(self):
        """Mark invoice payment as failed"""
        self.status = 'failed'
        self.updated_at = datetime.utcnow()
    
    def mark_cancelled(self):
        """Mark invoice as cancelled"""
        self.status = 'cancelled'
        self.updated_at = datetime.utcnow()
    
    def is_overdue(self):
        """Check if invoice is overdue"""
        if self.status == 'paid':
            return False
        
        return date.today() > self.due_date
    
    def days_overdue(self):
        """Get number of days overdue"""
        if not self.is_overdue():
            return 0
        
        return (date.today() - self.due_date).days
    
    def days_until_due(self):
        """Get number of days until due"""
        if self.is_overdue():
            return 0
        
        return (self.due_date - date.today()).days
    
    @staticmethod
    def find_by_company(company_id, status=None):
        """Find invoices for a company"""
        query = Invoice.query.filter_by(company_id=company_id)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(Invoice.created_at.desc()).all()
    
    @staticmethod
    def find_overdue_invoices():
        """Find all overdue invoices"""
        return Invoice.query.filter(
            Invoice.due_date < date.today(),
            Invoice.status.in_(['pending', 'failed'])
        ).all()
    
    @staticmethod
    def get_monthly_revenue(year, month):
        """Get total revenue for a specific month"""
        from sqlalchemy import func, extract
        
        result = db.session.query(
            func.sum(Invoice.total_amount)
        ).filter(
            Invoice.status == 'paid',
            extract('year', Invoice.paid_at) == year,
            extract('month', Invoice.paid_at) == month
        ).scalar()
        
        return float(result) if result else 0.0
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


class UsageTracking(db.Model):
    __tablename__ = 'usage_tracking'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    subscription_id = db.Column(db.String(36), db.ForeignKey('subscriptions.id'), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    chatbots_used = db.Column(db.Integer, nullable=False, default=0)
    conversations_count = db.Column(db.Integer, nullable=False, default=0)
    messages_sent = db.Column(db.Integer, nullable=False, default=0)
    messages_received = db.Column(db.Integer, nullable=False, default=0)
    api_calls_count = db.Column(db.Integer, nullable=False, default=0)
    storage_used_mb = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('company_id', 'period_start', 'period_end'),)
    
    def __init__(self, company_id, subscription_id, period_start, period_end, **kwargs):
        self.company_id = company_id
        self.subscription_id = subscription_id
        self.period_start = period_start
        self.period_end = period_end
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        """Convert usage tracking to dictionary"""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'subscription_id': self.subscription_id,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'chatbots_used': self.chatbots_used,
            'conversations_count': self.conversations_count,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'total_messages': self.messages_sent + self.messages_received,
            'api_calls_count': self.api_calls_count,
            'storage_used_mb': self.storage_used_mb,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def increment_conversations(self, count=1):
        """Increment conversation count"""
        self.conversations_count += count
        self.updated_at = datetime.utcnow()
    
    def increment_messages_sent(self, count=1):
        """Increment sent messages count"""
        self.messages_sent += count
        self.updated_at = datetime.utcnow()
    
    def increment_messages_received(self, count=1):
        """Increment received messages count"""
        self.messages_received += count
        self.updated_at = datetime.utcnow()
    
    def increment_api_calls(self, count=1):
        """Increment API calls count"""
        self.api_calls_count += count
        self.updated_at = datetime.utcnow()
    
    def update_storage_usage(self, mb_used):
        """Update storage usage"""
        self.storage_used_mb = mb_used
        self.updated_at = datetime.utcnow()
    
    @staticmethod
    def get_or_create_current_period(company_id, subscription_id):
        """Get or create usage tracking for current billing period"""
        from .subscription import Subscription
        
        subscription = Subscription.query.get(subscription_id)
        if not subscription:
            return None
        
        period_start = subscription.current_period_start.date()
        period_end = subscription.current_period_end.date()
        
        usage = UsageTracking.query.filter_by(
            company_id=company_id,
            subscription_id=subscription_id,
            period_start=period_start,
            period_end=period_end
        ).first()
        
        if not usage:
            usage = UsageTracking(
                company_id=company_id,
                subscription_id=subscription_id,
                period_start=period_start,
                period_end=period_end
            )
            db.session.add(usage)
        
        return usage
    
    def __repr__(self):
        return f'<UsageTracking {self.company_id} - {self.period_start} to {self.period_end}>'

