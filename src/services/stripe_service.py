import stripe
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class StripeService:
    """Service for integrating with Stripe payment processing"""
    
    def __init__(self):
        self.api_key = os.environ.get('STRIPE_SECRET_KEY')
        self.publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY')
        self.webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        if not self.api_key:
            logger.warning("STRIPE_SECRET_KEY not configured")
        else:
            stripe.api_key = self.api_key
    
    def create_customer(self, email: str, name: str, metadata: Dict = None) -> Dict:
        """Create a new Stripe customer"""
        try:
            customer_data = {
                'email': email,
                'name': name
            }
            
            if metadata:
                customer_data['metadata'] = metadata
            
            customer = stripe.Customer.create(**customer_data)
            logger.info(f"Created Stripe customer: {customer.id} for {email}")
            return customer
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {str(e)}")
            raise Exception(f"Failed to create customer: {str(e)}")
    
    def get_customer(self, customer_id: str) -> Dict:
        """Get customer details"""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get customer {customer_id}: {str(e)}")
            raise Exception(f"Failed to get customer: {str(e)}")
    
    def update_customer(self, customer_id: str, **kwargs) -> Dict:
        """Update customer information"""
        try:
            customer = stripe.Customer.modify(customer_id, **kwargs)
            logger.info(f"Updated Stripe customer: {customer_id}")
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update customer {customer_id}: {str(e)}")
            raise Exception(f"Failed to update customer: {str(e)}")
    
    def create_product(self, name: str, description: str = None, metadata: Dict = None) -> Dict:
        """Create a new product"""
        try:
            product_data = {
                'name': name,
                'type': 'service'
            }
            
            if description:
                product_data['description'] = description
            if metadata:
                product_data['metadata'] = metadata
            
            product = stripe.Product.create(**product_data)
            logger.info(f"Created Stripe product: {product.id}")
            return product
            
        except stripe.error.StripeError as e:
            logger.error(f"Product creation failed: {str(e)}")
            raise Exception(f"Failed to create product: {str(e)}")
    
    def create_price(self, product_id: str, amount: int, currency: str = 'usd', 
                    interval: str = 'month', interval_count: int = 1, metadata: Dict = None) -> Dict:
        """Create a price for a product"""
        try:
            price_data = {
                'product': product_id,
                'unit_amount': amount,  # Amount in cents
                'currency': currency,
                'recurring': {
                    'interval': interval,
                    'interval_count': interval_count
                }
            }
            
            if metadata:
                price_data['metadata'] = metadata
            
            price = stripe.Price.create(**price_data)
            logger.info(f"Created Stripe price: {price.id} for product {product_id}")
            return price
            
        except stripe.error.StripeError as e:
            logger.error(f"Price creation failed: {str(e)}")
            raise Exception(f"Failed to create price: {str(e)}")
    
    def create_subscription(self, customer_id: str, price_id: str, metadata: Dict = None,
                          trial_period_days: int = None) -> Dict:
        """Create a subscription"""
        try:
            subscription_data = {
                'customer': customer_id,
                'items': [{'price': price_id}],
                'payment_behavior': 'default_incomplete',
                'payment_settings': {'save_default_payment_method': 'on_subscription'},
                'expand': ['latest_invoice.payment_intent']
            }
            
            if metadata:
                subscription_data['metadata'] = metadata
            if trial_period_days:
                subscription_data['trial_period_days'] = trial_period_days
            
            subscription = stripe.Subscription.create(**subscription_data)
            logger.info(f"Created subscription: {subscription.id} for customer {customer_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            raise Exception(f"Failed to create subscription: {str(e)}")
    
    def get_subscription(self, subscription_id: str) -> Dict:
        """Get subscription details"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get subscription {subscription_id}: {str(e)}")
            raise Exception(f"Failed to get subscription: {str(e)}")
    
    def update_subscription(self, subscription_id: str, **kwargs) -> Dict:
        """Update subscription"""
        try:
            subscription = stripe.Subscription.modify(subscription_id, **kwargs)
            logger.info(f"Updated subscription: {subscription_id}")
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription {subscription_id}: {str(e)}")
            raise Exception(f"Failed to update subscription: {str(e)}")
    
    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Dict:
        """Cancel a subscription"""
        try:
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.delete(subscription_id)
            
            logger.info(f"Cancelled subscription: {subscription_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {str(e)}")
            raise Exception(f"Failed to cancel subscription: {str(e)}")
    
    def create_payment_intent(self, amount: int, currency: str = 'usd', 
                            customer_id: str = None, metadata: Dict = None) -> Dict:
        """Create a payment intent for one-time payments"""
        try:
            payment_data = {
                'amount': amount,
                'currency': currency,
                'automatic_payment_methods': {'enabled': True}
            }
            
            if customer_id:
                payment_data['customer'] = customer_id
            if metadata:
                payment_data['metadata'] = metadata
            
            payment_intent = stripe.PaymentIntent.create(**payment_data)
            logger.info(f"Created payment intent: {payment_intent.id}")
            return payment_intent
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            raise Exception(f"Failed to create payment intent: {str(e)}")
    
    def create_setup_intent(self, customer_id: str, metadata: Dict = None) -> Dict:
        """Create a setup intent for saving payment methods"""
        try:
            setup_data = {
                'customer': customer_id,
                'payment_method_types': ['card'],
                'usage': 'off_session'
            }
            
            if metadata:
                setup_data['metadata'] = metadata
            
            setup_intent = stripe.SetupIntent.create(**setup_data)
            logger.info(f"Created setup intent: {setup_intent.id}")
            return setup_intent
            
        except stripe.error.StripeError as e:
            logger.error(f"Setup intent creation failed: {str(e)}")
            raise Exception(f"Failed to create setup intent: {str(e)}")
    
    def get_payment_methods(self, customer_id: str, type: str = 'card') -> List[Dict]:
        """Get customer's payment methods"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type=type
            )
            return payment_methods.data
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get payment methods for {customer_id}: {str(e)}")
            raise Exception(f"Failed to get payment methods: {str(e)}")
    
    def detach_payment_method(self, payment_method_id: str) -> Dict:
        """Detach a payment method from customer"""
        try:
            payment_method = stripe.PaymentMethod.detach(payment_method_id)
            logger.info(f"Detached payment method: {payment_method_id}")
            return payment_method
        except stripe.error.StripeError as e:
            logger.error(f"Failed to detach payment method {payment_method_id}: {str(e)}")
            raise Exception(f"Failed to detach payment method: {str(e)}")
    
    def create_invoice(self, customer_id: str, description: str = None, 
                      metadata: Dict = None, auto_advance: bool = True) -> Dict:
        """Create an invoice"""
        try:
            invoice_data = {
                'customer': customer_id,
                'auto_advance': auto_advance
            }
            
            if description:
                invoice_data['description'] = description
            if metadata:
                invoice_data['metadata'] = metadata
            
            invoice = stripe.Invoice.create(**invoice_data)
            logger.info(f"Created invoice: {invoice.id}")
            return invoice
            
        except stripe.error.StripeError as e:
            logger.error(f"Invoice creation failed: {str(e)}")
            raise Exception(f"Failed to create invoice: {str(e)}")
    
    def add_invoice_item(self, customer_id: str, amount: int, description: str,
                        currency: str = 'usd', metadata: Dict = None) -> Dict:
        """Add an item to an invoice"""
        try:
            item_data = {
                'customer': customer_id,
                'amount': amount,
                'currency': currency,
                'description': description
            }
            
            if metadata:
                item_data['metadata'] = metadata
            
            invoice_item = stripe.InvoiceItem.create(**item_data)
            logger.info(f"Created invoice item: {invoice_item.id}")
            return invoice_item
            
        except stripe.error.StripeError as e:
            logger.error(f"Invoice item creation failed: {str(e)}")
            raise Exception(f"Failed to create invoice item: {str(e)}")
    
    def finalize_invoice(self, invoice_id: str) -> Dict:
        """Finalize an invoice"""
        try:
            invoice = stripe.Invoice.finalize_invoice(invoice_id)
            logger.info(f"Finalized invoice: {invoice_id}")
            return invoice
        except stripe.error.StripeError as e:
            logger.error(f"Failed to finalize invoice {invoice_id}: {str(e)}")
            raise Exception(f"Failed to finalize invoice: {str(e)}")
    
    def pay_invoice(self, invoice_id: str) -> Dict:
        """Pay an invoice"""
        try:
            invoice = stripe.Invoice.pay(invoice_id)
            logger.info(f"Paid invoice: {invoice_id}")
            return invoice
        except stripe.error.StripeError as e:
            logger.error(f"Failed to pay invoice {invoice_id}: {str(e)}")
            raise Exception(f"Failed to pay invoice: {str(e)}")
    
    def get_usage_records(self, subscription_item_id: str, limit: int = 100) -> List[Dict]:
        """Get usage records for metered billing"""
        try:
            usage_records = stripe.UsageRecord.list(
                subscription_item=subscription_item_id,
                limit=limit
            )
            return usage_records.data
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get usage records: {str(e)}")
            raise Exception(f"Failed to get usage records: {str(e)}")
    
    def create_usage_record(self, subscription_item_id: str, quantity: int, 
                          timestamp: int = None, action: str = 'increment') -> Dict:
        """Create a usage record for metered billing"""
        try:
            usage_data = {
                'quantity': quantity,
                'action': action
            }
            
            if timestamp:
                usage_data['timestamp'] = timestamp
            else:
                usage_data['timestamp'] = int(datetime.utcnow().timestamp())
            
            usage_record = stripe.UsageRecord.create(
                subscription_item_id,
                **usage_data
            )
            logger.info(f"Created usage record: {usage_record.id}")
            return usage_record
            
        except stripe.error.StripeError as e:
            logger.error(f"Usage record creation failed: {str(e)}")
            raise Exception(f"Failed to create usage record: {str(e)}")
    
    def construct_webhook_event(self, payload: bytes, signature: str) -> Dict:
        """Construct and verify webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            logger.info(f"Verified webhook event: {event['type']}")
            return event
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            raise Exception("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            raise Exception("Invalid signature")
    
    def get_subscription_usage_summary(self, subscription_id: str) -> Dict:
        """Get usage summary for a subscription"""
        try:
            subscription = self.get_subscription(subscription_id)
            usage_summary = {
                'subscription_id': subscription_id,
                'status': subscription.status,
                'current_period_start': subscription.current_period_start,
                'current_period_end': subscription.current_period_end,
                'items': []
            }
            
            for item in subscription.items.data:
                item_summary = {
                    'id': item.id,
                    'price_id': item.price.id,
                    'quantity': item.quantity,
                    'amount': item.price.unit_amount,
                    'currency': item.price.currency
                }
                
                # Get usage records if it's a metered price
                if item.price.billing_scheme == 'per_unit' and item.price.recurring.usage_type == 'metered':
                    usage_records = self.get_usage_records(item.id, limit=10)
                    item_summary['usage_records'] = usage_records
                
                usage_summary['items'].append(item_summary)
            
            return usage_summary
            
        except Exception as e:
            logger.error(f"Failed to get usage summary: {str(e)}")
            raise
    
    def calculate_proration_amount(self, subscription_id: str, new_price_id: str) -> int:
        """Calculate proration amount for subscription change"""
        try:
            # Get current subscription
            subscription = self.get_subscription(subscription_id)
            
            # Create preview of the upcoming invoice with the change
            upcoming_invoice = stripe.Invoice.upcoming(
                customer=subscription.customer,
                subscription=subscription_id,
                subscription_items=[{
                    'id': subscription.items.data[0].id,
                    'price': new_price_id
                }]
            )
            
            return upcoming_invoice.amount_due
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to calculate proration: {str(e)}")
            raise Exception(f"Failed to calculate proration: {str(e)}")

# Global instance
stripe_service = StripeService()

