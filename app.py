import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from src.config import config
from src.models import db

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    
    # Import all models after db initialization to avoid circular imports
    from src.models.user import User, CompanyUser
    from src.models.company import Company
    from src.models.subscription import Subscription, SubscriptionPlan
    from src.models.chatbot import Chatbot
    from src.models.conversation import Conversation, Message
    from src.models.analytics import AnalyticsEvent
    from src.models.webhook import WebhookEvent
    from src.models.invoice import Invoice, UsageTracking
    
    # Create database tables after all models are imported
    with app.app_context():
        db.create_all()
        
        # Create default subscription plans if they don't exist
        if SubscriptionPlan.query.count() == 0:
            create_default_plans()
    # Import blueprints after models
    from src.routes.auth import auth_bp, check_if_token_revoked
    from src.routes.companies import companies_bp
    from src.routes.chatbots import chatbots_bp
    from src.routes.conversations import conversations_bp
    from src.routes.webhooks import webhooks_bp
    from src.routes.integrations import integrations_bp
    from src.routes.billing import billing_bp
    
    # Initialize CORS
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    # JWT token blacklist checker
    @jwt.token_in_blocklist_loader
    def check_if_token_is_revoked(jwt_header, jwt_payload):
        return check_if_token_revoked(jwt_header, jwt_payload)
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token'}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization token is required'}), 401
    
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has been revoked'}), 401
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(companies_bp, url_prefix='/api/companies')
    app.register_blueprint(chatbots_bp, url_prefix='/api/chatbots')
    app.register_blueprint(conversations_bp, url_prefix='/api/conversations')
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
    app.register_blueprint(integrations_bp, url_prefix='/api/integrations')
    app.register_blueprint(billing_bp, url_prefix='/api/billing')
    
    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'service': 'WhatsApp Chatbot SaaS API',
            'version': '1.0.0'
        }), 200
    
    # API info endpoint
    @app.route('/api', methods=['GET'])
    def api_info():
        return jsonify({
            'service': 'WhatsApp Chatbot SaaS API',
            'version': '1.0.0',
            'endpoints': {
                'auth': '/api/auth',
                'companies': '/api/companies',
                'chatbots': '/api/chatbots',
                'conversations': '/api/conversations',
                'webhooks': '/api/webhooks',
                'integrations': '/api/integrations',
                'billing': '/api/billing',
                'health': '/api/health'
            },
            'documentation': 'https://docs.example.com/api'
        }), 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request'}), 400
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Access forbidden'}), 403
    
    # Frontend serving routes
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        static_folder_path = app.static_folder
        if static_folder_path is None:
            return jsonify({'error': 'Static folder not configured'}), 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                # Return API info if no frontend is available
                return jsonify({
                    'service': 'WhatsApp Chatbot SaaS API',
                    'message': 'Frontend not available. Use /api endpoints for API access.',
                    'api_docs': '/api'
                }), 200
    
    return app

def create_default_plans():
    """Create default subscription plans"""
    from src.models.subscription import SubscriptionPlan
    from src.models import db
    
    plans = [
        {
            'name': 'Starter Plan',
            'plan_type': 'starter',
            'description': 'Perfect for small businesses getting started with WhatsApp automation',
            'price_monthly': 29.99,
            'price_yearly': 299.99,
            'max_chatbots': 1,
            'max_conversations_per_month': 500,
            'max_messages_per_month': 2000,
            'features': {
                'analytics': True,
                'templates': 5,
                'support': 'email'
            }
        },
        {
            'name': 'Business Plan',
            'plan_type': 'business',
            'description': 'Ideal for growing businesses with multiple chatbots and advanced features',
            'price_monthly': 99.99,
            'price_yearly': 999.99,
            'max_chatbots': 5,
            'max_conversations_per_month': 2000,
            'max_messages_per_month': 10000,
            'features': {
                'analytics': True,
                'templates': 20,
                'support': 'priority',
                'custom_branding': True,
                'api_access': True
            }
        },
        {
            'name': 'Enterprise Plan',
            'plan_type': 'enterprise',
            'description': 'For large organizations requiring unlimited chatbots and premium support',
            'price_monthly': 299.99,
            'price_yearly': 2999.99,
            'max_chatbots': -1,  # Unlimited
            'max_conversations_per_month': 10000,
            'max_messages_per_month': 50000,
            'features': {
                'analytics': True,
                'templates': -1,  # Unlimited
                'support': 'dedicated',
                'custom_branding': True,
                'api_access': True,
                'white_label': True,
                'sla': True
            }
        }
    ]
    
    for plan_data in plans:
        plan = SubscriptionPlan(**plan_data)
        db.session.add(plan)
    
    db.session.commit()
    print("Default subscription plans created successfully")

# Create the Flask app
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

