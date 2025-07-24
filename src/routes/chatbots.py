from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from src.models import db
from src.models.user import User
from src.models.company import Company
from src.models.chatbot import Chatbot
from src.models.conversation import Conversation, Message
from src.models.analytics import AnalyticsEvent, AnalyticsEventTypes

chatbots_bp = Blueprint('chatbots', __name__)

@chatbots_bp.route('/', methods=['GET'])
@jwt_required()
def get_chatbots():
    """Get chatbots for a company"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company_id = request.args.get('company_id')
        if not company_id:
            return jsonify({'error': 'company_id parameter is required'}), 400
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company.id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get chatbots
        chatbots = Chatbot.find_by_company(company_id)
        
        chatbots_data = []
        for chatbot in chatbots:
            chatbot_data = chatbot.to_dict(include_stats=True)
            chatbots_data.append(chatbot_data)
        
        return jsonify({
            'chatbots': chatbots_data,
            'total': len(chatbots_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get chatbots error: {str(e)}")
        return jsonify({'error': 'Failed to get chatbots'}), 500

@chatbots_bp.route('/', methods=['POST'])
@jwt_required()
def create_chatbot():
    """Create a new chatbot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        company_id = data.get('company_id')
        
        if not company_id:
            return jsonify({'error': 'company_id is required'}), 400
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company.id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if company can create more chatbots
        if not company.can_create_chatbot():
            return jsonify({'error': 'Chatbot limit reached for current subscription plan'}), 403
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        
        # Create chatbot
        chatbot = Chatbot(
            company_id=company_id,
            name=data['name'].strip(),
            description=data.get('description', '').strip(),
            welcome_message=data.get('welcome_message'),
            fallback_message=data.get('fallback_message'),
            auto_response_enabled=data.get('auto_response_enabled', True),
            human_handoff_enabled=data.get('human_handoff_enabled', False),
            analytics_enabled=data.get('analytics_enabled', True)
        )
        
        # Update configuration if provided
        if data.get('configuration'):
            chatbot.update_configuration(data['configuration'])
        
        # Update business hours if provided
        if data.get('business_hours'):
            chatbot.business_hours = data['business_hours']
        
        db.session.add(chatbot)
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=company_id,
            event_name=AnalyticsEventTypes.CHATBOT_CREATED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'chatbot_name': chatbot.name,
                'company_name': company.name
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Chatbot created successfully',
            'chatbot': chatbot.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create chatbot error: {str(e)}")
        return jsonify({'error': 'Failed to create chatbot'}), 500

@chatbots_bp.route('/<chatbot_id>', methods=['GET'])
@jwt_required()
def get_chatbot(chatbot_id):
    """Get a specific chatbot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        chatbot_data = chatbot.to_dict(include_stats=True)
        
        # Include validation status
        whatsapp_errors = chatbot.validate_whatsapp_setup()
        botpress_errors = chatbot.validate_botpress_setup()
        
        chatbot_data['validation'] = {
            'whatsapp_setup_valid': len(whatsapp_errors) == 0,
            'whatsapp_errors': whatsapp_errors,
            'botpress_setup_valid': len(botpress_errors) == 0,
            'botpress_errors': botpress_errors
        }
        
        return jsonify({'chatbot': chatbot_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get chatbot error: {str(e)}")
        return jsonify({'error': 'Failed to get chatbot'}), 500

@chatbots_bp.route('/<chatbot_id>', methods=['PUT'])
@jwt_required()
def update_chatbot(chatbot_id):
    """Update a chatbot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Update allowed fields
        allowed_fields = [
            'name', 'description', 'welcome_message', 'fallback_message',
            'auto_response_enabled', 'human_handoff_enabled', 'analytics_enabled',
            'whatsapp_phone_number', 'whatsapp_phone_number_id', 
            'whatsapp_business_account_id', 'botpress_bot_id'
        ]
        
        for field in allowed_fields:
            if field in data:
                setattr(chatbot, field, data[field])
        
        # Update configuration if provided
        if 'configuration' in data:
            chatbot.update_configuration(data['configuration'])
        
        # Update business hours if provided
        if 'business_hours' in data:
            chatbot.business_hours = data['business_hours']
        
        chatbot.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Chatbot updated successfully',
            'chatbot': chatbot.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update chatbot error: {str(e)}")
        return jsonify({'error': 'Failed to update chatbot'}), 500

@chatbots_bp.route('/<chatbot_id>', methods=['DELETE'])
@jwt_required()
def delete_chatbot(chatbot_id):
    """Delete a chatbot (soft delete)"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Soft delete the chatbot
        chatbot.soft_delete()
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.CHATBOT_DELETED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'chatbot_name': chatbot.name
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({'message': 'Chatbot deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete chatbot error: {str(e)}")
        return jsonify({'error': 'Failed to delete chatbot'}), 500

@chatbots_bp.route('/<chatbot_id>/deploy', methods=['POST'])
@jwt_required()
def deploy_chatbot(chatbot_id):
    """Deploy a chatbot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Validate setup before deployment
        whatsapp_errors = chatbot.validate_whatsapp_setup()
        botpress_errors = chatbot.validate_botpress_setup()
        
        if whatsapp_errors or botpress_errors:
            return jsonify({
                'error': 'Chatbot setup is incomplete',
                'whatsapp_errors': whatsapp_errors,
                'botpress_errors': botpress_errors
            }), 400
        
        # Deploy the chatbot
        chatbot.deploy()
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.CHATBOT_DEPLOYED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'chatbot_name': chatbot.name
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Chatbot deployed successfully',
            'chatbot': chatbot.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Deploy chatbot error: {str(e)}")
        return jsonify({'error': 'Failed to deploy chatbot'}), 500

@chatbots_bp.route('/<chatbot_id>/deactivate', methods=['POST'])
@jwt_required()
def deactivate_chatbot(chatbot_id):
    """Deactivate a chatbot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Deactivate the chatbot
        chatbot.deactivate()
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.CHATBOT_DEACTIVATED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'chatbot_name': chatbot.name
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Chatbot deactivated successfully',
            'chatbot': chatbot.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Deactivate chatbot error: {str(e)}")
        return jsonify({'error': 'Failed to deactivate chatbot'}), 500

@chatbots_bp.route('/<chatbot_id>/conversations', methods=['GET'])
@jwt_required()
def get_chatbot_conversations(chatbot_id):
    """Get conversations for a chatbot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        status = request.args.get('status', 'open')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Query conversations
        query = Conversation.query.filter_by(chatbot_id=chatbot_id)
        
        if status != 'all':
            query = query.filter_by(status=status)
        
        # Paginate
        conversations = query.order_by(Conversation.last_message_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        conversations_data = [conv.to_dict() for conv in conversations.items]
        
        return jsonify({
            'conversations': conversations_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': conversations.total,
                'pages': conversations.pages,
                'has_next': conversations.has_next,
                'has_prev': conversations.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get chatbot conversations error: {str(e)}")
        return jsonify({'error': 'Failed to get conversations'}), 500

@chatbots_bp.route('/<chatbot_id>/stats', methods=['GET'])
@jwt_required()
def get_chatbot_stats(chatbot_id):
    """Get detailed statistics for a chatbot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        
        # Get basic stats
        stats = chatbot.get_stats(days=days)
        
        # Get additional statistics
        from datetime import timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Message type distribution
        message_types = db.session.query(
            Message.type,
            func.count(Message.id).label('count')
        ).join(Conversation).filter(
            Conversation.chatbot_id == chatbot_id,
            Message.created_at >= cutoff_date
        ).group_by(Message.type).all()
        
        # Daily conversation counts
        daily_conversations = db.session.query(
            func.date(Conversation.started_at).label('date'),
            func.count(Conversation.id).label('count')
        ).filter(
            Conversation.chatbot_id == chatbot_id,
            Conversation.started_at >= cutoff_date
        ).group_by(func.date(Conversation.started_at)).all()
        
        # Response time analysis (simplified)
        avg_response_time = 5  # Placeholder - would need more complex query
        
        stats.update({
            'message_type_distribution': [
                {'type': mt.type, 'count': mt.count}
                for mt in message_types
            ],
            'daily_conversations': [
                {'date': str(dc.date), 'count': dc.count}
                for dc in daily_conversations
            ],
            'avg_response_time_minutes': avg_response_time
        })
        
        return jsonify({
            'chatbot_id': chatbot_id,
            'stats': stats
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get chatbot stats error: {str(e)}")
        return jsonify({'error': 'Failed to get chatbot statistics'}), 500

