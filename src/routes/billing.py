from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import json

from src.models import db
from src.models.user import User
from src.models.company import Company
from src.models.subscription import Subscription, SubscriptionPlan
from src.models.invoice import Invoice
from src.models.analytics import AnalyticsEvent, AnalyticsEventTypes
from src.services.stripe_service import stripe_service

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/plans', methods=['GET'])
def get_subscription_plans():
    """Get all available subscription plans"""
    try:
        plans = SubscriptionPlan.query.filter_by(active=True).all()
        
        plans_data = []
        for plan in plans:
            plan_dict = plan.to_dict()
            
            # Add feature comparison
            features = {
                'chatbots_limit': plan.chatbots_limit,
                'messages_limit': plan.messages_limit,
                'users_limit': plan.users_limit,
                'storage_limit_gb': plan.storage_limit_gb,
                'analytics_retention_days': plan.analytics_retention_days,
                'priority_support': plan.priority_support,
                'custom_branding': plan.custom_branding,
                'api_access': plan.api_access,
                'webhook_support': plan.webhook_support
            }
            plan_dict['features'] = features
            plans_data.append(plan_dict)
        
        return jsonify({
            'plans': plans_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get subscription plans error: {str(e)}")
        return jsonify({'error': 'Failed to get subscription plans'}), 500

@billing_bp.route('/current-subscription', methods=['GET'])
@jwt_required()
def get_current_subscription():
    """Get current user's subscription details"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user's companies and their subscriptions
        user_companies = user.get_companies()
        subscriptions_data = []
        
        for company_data in user_companies:
            company = company_data['company']
            subscription = Subscription.query.filter_by(
                company_id=company.id,
                status__in=['active', 'trialing', 'past_due']
            ).first()
            
            if subscription:
                subscription_dict = subscription.to_dict()
                subscription_dict['company'] = {
                    'id': company.id,
                    'name': company.name,
                    'role': company_data['role']
                }
                
                # Get usage information
                usage_info = subscription.get_usage_info()
                subscription_dict['usage'] = usage_info
                
                # Get Stripe subscription details if available
                if subscription.stripe_subscription_id:
                    try:
                        stripe_subscription = stripe_service.get_subscription(subscription.stripe_subscription_id)
                        subscription_dict['stripe_status'] = stripe_subscription.status
                        subscription_dict['next_billing_date'] = stripe_subscription.current_period_end
                    except Exception as e:
                        current_app.logger.warning(f"Failed to get Stripe subscription: {str(e)}")
                
                subscriptions_data.append(subscription_dict)
        
        return jsonify({
            'subscriptions': subscriptions_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get current subscription error: {str(e)}")
        return jsonify({'error': 'Failed to get subscription details'}), 500

@billing_bp.route('/subscribe', methods=['POST'])
@jwt_required()
def create_subscription():
    """Create a new subscription"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        company_id = data.get('company_id')
        plan_id = data.get('plan_id')
        payment_method_id = data.get('payment_method_id')
        
        if not all([company_id, plan_id]):
            return jsonify({'error': 'company_id and plan_id are required'}), 400
        
        # Verify user has access to company
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get subscription plan
        plan = SubscriptionPlan.find_by_id(plan_id)
        if not plan or not plan.active:
            return jsonify({'error': 'Invalid subscription plan'}), 400
        
        # Check if company already has an active subscription
        existing_subscription = Subscription.query.filter_by(
            company_id=company_id,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        if existing_subscription:
            return jsonify({'error': 'Company already has an active subscription'}), 400
        
        # Create or get Stripe customer
        stripe_customer_id = company.stripe_customer_id
        if not stripe_customer_id:
            stripe_customer = stripe_service.create_customer(
                email=user.email,
                name=company.name,
                metadata={
                    'company_id': str(company_id),
                    'user_id': str(user_id)
                }
            )
            stripe_customer_id = stripe_customer.id
            company.stripe_customer_id = stripe_customer_id
        
        # Create Stripe subscription
        stripe_subscription = stripe_service.create_subscription(
            customer_id=stripe_customer_id,
            price_id=plan.stripe_price_id,
            metadata={
                'company_id': str(company_id),
                'plan_id': str(plan_id),
                'user_id': str(user_id)
            },
            trial_period_days=plan.trial_days if plan.trial_days > 0 else None
        )
        
        # Create local subscription record
        subscription = Subscription(
            company_id=company_id,
            plan_id=plan_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription.id,
            status='incomplete',
            current_period_start=datetime.utcfromtimestamp(stripe_subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(stripe_subscription.current_period_end),
            trial_start=datetime.utcfromtimestamp(stripe_subscription.trial_start) if stripe_subscription.trial_start else None,
            trial_end=datetime.utcfromtimestamp(stripe_subscription.trial_end) if stripe_subscription.trial_end else None
        )
        
        db.session.add(subscription)
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=company_id,
            event_name=AnalyticsEventTypes.SUBSCRIPTION_CREATED,
            user_id=user_id,
            event_data={
                'plan_id': plan_id,
                'plan_name': plan.name,
                'stripe_subscription_id': stripe_subscription.id,
                'trial_days': plan.trial_days
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Subscription created successfully',
            'subscription': subscription.to_dict(),
            'client_secret': stripe_subscription.latest_invoice.payment_intent.client_secret if stripe_subscription.latest_invoice else None
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create subscription error: {str(e)}")
        return jsonify({'error': 'Failed to create subscription'}), 500

@billing_bp.route('/subscriptions/<int:subscription_id>/change-plan', methods=['POST'])
@jwt_required()
def change_subscription_plan(subscription_id):
    """Change subscription plan"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        new_plan_id = data.get('plan_id')
        
        if not new_plan_id:
            return jsonify({'error': 'plan_id is required'}), 400
        
        # Get subscription
        subscription = Subscription.find_by_id(subscription_id)
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if subscription.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get new plan
        new_plan = SubscriptionPlan.find_by_id(new_plan_id)
        if not new_plan or not new_plan.active:
            return jsonify({'error': 'Invalid subscription plan'}), 400
        
        # Calculate proration amount
        proration_amount = stripe_service.calculate_proration_amount(
            subscription.stripe_subscription_id,
            new_plan.stripe_price_id
        )
        
        # Update Stripe subscription
        stripe_subscription = stripe_service.update_subscription(
            subscription.stripe_subscription_id,
            items=[{
                'id': subscription.stripe_subscription_id,  # This should be the subscription item ID
                'price': new_plan.stripe_price_id
            }],
            proration_behavior='create_prorations'
        )
        
        # Update local subscription
        old_plan_name = subscription.plan.name
        subscription.plan_id = new_plan_id
        subscription.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=subscription.company_id,
            event_name=AnalyticsEventTypes.SUBSCRIPTION_UPDATED,
            user_id=user_id,
            event_data={
                'old_plan_name': old_plan_name,
                'new_plan_name': new_plan.name,
                'proration_amount': proration_amount
            }
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Subscription plan changed successfully',
            'subscription': subscription.to_dict(),
            'proration_amount': proration_amount
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Change subscription plan error: {str(e)}")
        return jsonify({'error': 'Failed to change subscription plan'}), 500

@billing_bp.route('/subscriptions/<int:subscription_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_subscription(subscription_id):
    """Cancel subscription"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        immediate = data.get('immediate', False)
        reason = data.get('reason', '')
        
        # Get subscription
        subscription = Subscription.find_by_id(subscription_id)
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if subscription.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Cancel Stripe subscription
        stripe_subscription = stripe_service.cancel_subscription(
            subscription.stripe_subscription_id,
            at_period_end=not immediate
        )
        
        # Update local subscription
        if immediate:
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
        else:
            subscription.cancel_at_period_end = True
            subscription.canceled_at = datetime.utcfromtimestamp(stripe_subscription.canceled_at) if stripe_subscription.canceled_at else None
        
        subscription.cancellation_reason = reason
        subscription.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=subscription.company_id,
            event_name=AnalyticsEventTypes.SUBSCRIPTION_CANCELED,
            user_id=user_id,
            event_data={
                'immediate': immediate,
                'reason': reason,
                'plan_name': subscription.plan.name
            }
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Subscription canceled successfully',
            'subscription': subscription.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Cancel subscription error: {str(e)}")
        return jsonify({'error': 'Failed to cancel subscription'}), 500

@billing_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """Get customer's payment methods"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.args
        company_id = data.get('company_id', type=int)
        
        if not company_id:
            return jsonify({'error': 'company_id is required'}), 400
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        company = Company.find_by_id(company_id)
        if not company or not company.stripe_customer_id:
            return jsonify({'payment_methods': []}), 200
        
        # Get payment methods from Stripe
        payment_methods = stripe_service.get_payment_methods(company.stripe_customer_id)
        
        return jsonify({
            'payment_methods': payment_methods
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get payment methods error: {str(e)}")
        return jsonify({'error': 'Failed to get payment methods'}), 500

@billing_bp.route('/setup-intent', methods=['POST'])
@jwt_required()
def create_setup_intent():
    """Create setup intent for saving payment method"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        company_id = data.get('company_id')
        
        if not company_id:
            return jsonify({'error': 'company_id is required'}), 400
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Create or get Stripe customer
        stripe_customer_id = company.stripe_customer_id
        if not stripe_customer_id:
            stripe_customer = stripe_service.create_customer(
                email=user.email,
                name=company.name,
                metadata={
                    'company_id': str(company_id),
                    'user_id': str(user_id)
                }
            )
            stripe_customer_id = stripe_customer.id
            company.stripe_customer_id = stripe_customer_id
            db.session.commit()
        
        # Create setup intent
        setup_intent = stripe_service.create_setup_intent(
            customer_id=stripe_customer_id,
            metadata={
                'company_id': str(company_id),
                'user_id': str(user_id)
            }
        )
        
        return jsonify({
            'client_secret': setup_intent.client_secret
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Create setup intent error: {str(e)}")
        return jsonify({'error': 'Failed to create setup intent'}), 500

@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_invoices():
    """Get company invoices"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company_id = request.args.get('company_id', type=int)
        limit = request.args.get('limit', 50, type=int)
        
        if not company_id:
            return jsonify({'error': 'company_id is required'}), 400
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get invoices from database
        invoices = Invoice.query.filter_by(company_id=company_id)\
                              .order_by(Invoice.created_at.desc())\
                              .limit(limit).all()
        
        invoices_data = [invoice.to_dict() for invoice in invoices]
        
        return jsonify({
            'invoices': invoices_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get invoices error: {str(e)}")
        return jsonify({'error': 'Failed to get invoices'}), 500

@billing_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage_statistics():
    """Get usage statistics for billing"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company_id = request.args.get('company_id', type=int)
        
        if not company_id:
            return jsonify({'error': 'company_id is required'}), 400
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Get current subscription
        subscription = Subscription.query.filter_by(
            company_id=company_id,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        if not subscription:
            return jsonify({'error': 'No active subscription found'}), 404
        
        # Get usage information
        usage_info = subscription.get_usage_info()
        
        # Get plan limits
        plan_limits = {
            'chatbots_limit': subscription.plan.chatbots_limit,
            'messages_limit': subscription.plan.messages_limit,
            'users_limit': subscription.plan.users_limit,
            'storage_limit_gb': subscription.plan.storage_limit_gb
        }
        
        return jsonify({
            'usage': usage_info,
            'limits': plan_limits,
            'subscription': subscription.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get usage statistics error: {str(e)}")
        return jsonify({'error': 'Failed to get usage statistics'}), 500

@billing_bp.route('/webhooks/stripe', methods=['POST'])
def handle_stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        payload = request.get_data()
        signature = request.headers.get('Stripe-Signature')
        
        # Construct and verify event
        event = stripe_service.construct_webhook_event(payload, signature)
        
        current_app.logger.info(f"Received Stripe webhook: {event['type']}")
        
        # Handle different event types
        if event['type'] == 'customer.subscription.created':
            handle_subscription_created(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            handle_subscription_updated(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            handle_subscription_deleted(event['data']['object'])
        elif event['type'] == 'invoice.payment_succeeded':
            handle_invoice_payment_succeeded(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            handle_invoice_payment_failed(event['data']['object'])
        elif event['type'] == 'customer.subscription.trial_will_end':
            handle_trial_will_end(event['data']['object'])
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Stripe webhook error: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def handle_subscription_created(stripe_subscription):
    """Handle subscription created event"""
    try:
        subscription = Subscription.query.filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()
        
        if subscription:
            subscription.status = stripe_subscription['status']
            subscription.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Updated subscription status: {subscription.id}")
    except Exception as e:
        current_app.logger.error(f"Handle subscription created error: {str(e)}")

def handle_subscription_updated(stripe_subscription):
    """Handle subscription updated event"""
    try:
        subscription = Subscription.query.filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()
        
        if subscription:
            subscription.status = stripe_subscription['status']
            subscription.current_period_start = datetime.utcfromtimestamp(stripe_subscription['current_period_start'])
            subscription.current_period_end = datetime.utcfromtimestamp(stripe_subscription['current_period_end'])
            subscription.updated_at = datetime.utcnow()
            
            if stripe_subscription.get('canceled_at'):
                subscription.canceled_at = datetime.utcfromtimestamp(stripe_subscription['canceled_at'])
            
            db.session.commit()
            
            current_app.logger.info(f"Updated subscription: {subscription.id}")
    except Exception as e:
        current_app.logger.error(f"Handle subscription updated error: {str(e)}")

def handle_subscription_deleted(stripe_subscription):
    """Handle subscription deleted event"""
    try:
        subscription = Subscription.query.filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()
        
        if subscription:
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            subscription.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Canceled subscription: {subscription.id}")
    except Exception as e:
        current_app.logger.error(f"Handle subscription deleted error: {str(e)}")

def handle_invoice_payment_succeeded(stripe_invoice):
    """Handle successful invoice payment"""
    try:
        # Create or update invoice record
        invoice = Invoice.query.filter_by(
            stripe_invoice_id=stripe_invoice['id']
        ).first()
        
        if not invoice:
            # Find subscription
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=stripe_invoice.get('subscription')
            ).first()
            
            if subscription:
                invoice = Invoice(
                    company_id=subscription.company_id,
                    subscription_id=subscription.id,
                    stripe_invoice_id=stripe_invoice['id'],
                    amount=stripe_invoice['amount_paid'],
                    currency=stripe_invoice['currency'],
                    status='paid',
                    paid_at=datetime.utcfromtimestamp(stripe_invoice['status_transitions']['paid_at'])
                )
                db.session.add(invoice)
        else:
            invoice.status = 'paid'
            invoice.paid_at = datetime.utcfromtimestamp(stripe_invoice['status_transitions']['paid_at'])
        
        db.session.commit()
        current_app.logger.info(f"Processed successful payment for invoice: {stripe_invoice['id']}")
        
    except Exception as e:
        current_app.logger.error(f"Handle invoice payment succeeded error: {str(e)}")

def handle_invoice_payment_failed(stripe_invoice):
    """Handle failed invoice payment"""
    try:
        # Update subscription status if needed
        subscription = Subscription.query.filter_by(
            stripe_subscription_id=stripe_invoice.get('subscription')
        ).first()
        
        if subscription:
            subscription.status = 'past_due'
            subscription.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.warning(f"Payment failed for subscription: {subscription.id}")
        
    except Exception as e:
        current_app.logger.error(f"Handle invoice payment failed error: {str(e)}")

def handle_trial_will_end(stripe_subscription):
    """Handle trial ending soon event"""
    try:
        subscription = Subscription.query.filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()
        
        if subscription:
            # Here you could send notification emails or take other actions
            current_app.logger.info(f"Trial ending soon for subscription: {subscription.id}")
        
    except Exception as e:
        current_app.logger.error(f"Handle trial will end error: {str(e)}")

