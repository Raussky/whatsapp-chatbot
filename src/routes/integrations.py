from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from src.models import db
from src.models.user import User
from src.models.chatbot import Chatbot
from src.models.analytics import AnalyticsEvent, AnalyticsEventTypes
from src.services.botpress_service import botpress_service
from src.services.whatsapp_service import whatsapp_service

integrations_bp = Blueprint('integrations', __name__)

@integrations_bp.route('/botpress/bots', methods=['POST'])
@jwt_required()
def create_botpress_bot():
    """Create a new bot in Botpress"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        chatbot_id = data.get('chatbot_id')
        
        if not chatbot_id:
            return jsonify({'error': 'chatbot_id is required'}), 400
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Create bot in Botpress
        bot_name = f"{chatbot.name} - {chatbot.company.name}"
        bot_description = chatbot.description or f"WhatsApp chatbot for {chatbot.company.name}"
        
        botpress_bot = botpress_service.create_bot(
            name=bot_name,
            description=bot_description
        )
        
        # Update chatbot with Botpress bot ID
        chatbot.botpress_bot_id = botpress_bot.get('bot', {}).get('id')
        chatbot.updated_at = datetime.utcnow()
        
        # Create webhook for the bot
        webhook_url = f"{request.host_url}api/webhooks/botpress"
        try:
            webhook = botpress_service.create_webhook(
                chatbot.botpress_bot_id,
                webhook_url
            )
            chatbot.botpress_webhook_id = webhook.get('webhook', {}).get('id')
        except Exception as e:
            current_app.logger.warning(f"Failed to create Botpress webhook: {str(e)}")
        
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.INTEGRATION_CONNECTED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'integration_type': 'botpress',
                'bot_id': chatbot.botpress_bot_id,
                'bot_name': bot_name
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Botpress bot created successfully',
            'bot': botpress_bot,
            'chatbot': chatbot.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create Botpress bot error: {str(e)}")
        return jsonify({'error': 'Failed to create Botpress bot'}), 500

@integrations_bp.route('/botpress/bots/<bot_id>', methods=['GET'])
@jwt_required()
def get_botpress_bot(bot_id):
    """Get Botpress bot details"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find chatbot by Botpress bot ID
        chatbot = Chatbot.query.filter_by(botpress_bot_id=bot_id).first()
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get bot details from Botpress
        bot_details = botpress_service.get_bot(bot_id)
        
        return jsonify({
            'bot': bot_details,
            'chatbot': chatbot.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get Botpress bot error: {str(e)}")
        return jsonify({'error': 'Failed to get Botpress bot details'}), 500

@integrations_bp.route('/botpress/bots/<bot_id>/train', methods=['POST'])
@jwt_required()
def train_botpress_bot(bot_id):
    """Train Botpress bot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find chatbot by Botpress bot ID
        chatbot = Chatbot.query.filter_by(botpress_bot_id=bot_id).first()
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Train bot in Botpress
        training_result = botpress_service.train_bot(bot_id)
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.BOT_TRAINED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'bot_id': bot_id,
                'training_result': training_result
            }
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Bot training started',
            'training_result': training_result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Train Botpress bot error: {str(e)}")
        return jsonify({'error': 'Failed to train bot'}), 500

@integrations_bp.route('/botpress/bots/<bot_id>/training-status', methods=['GET'])
@jwt_required()
def get_botpress_training_status(bot_id):
    """Get Botpress bot training status"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find chatbot by Botpress bot ID
        chatbot = Chatbot.query.filter_by(botpress_bot_id=bot_id).first()
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get training status from Botpress
        training_status = botpress_service.get_training_status(bot_id)
        
        return jsonify({
            'training_status': training_status
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get training status error: {str(e)}")
        return jsonify({'error': 'Failed to get training status'}), 500

@integrations_bp.route('/botpress/bots/<bot_id>/intents', methods=['POST'])
@jwt_required()
def create_botpress_intent(bot_id):
    """Create intent for Botpress bot"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find chatbot by Botpress bot ID
        chatbot = Chatbot.query.filter_by(botpress_bot_id=bot_id).first()
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('utterances') or not data.get('responses'):
            return jsonify({'error': 'name, utterances, and responses are required'}), 400
        
        # Create intent in Botpress
        intent = botpress_service.create_intent(
            bot_id,
            data['name'],
            data['utterances'],
            data['responses']
        )
        
        return jsonify({
            'message': 'Intent created successfully',
            'intent': intent
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Create Botpress intent error: {str(e)}")
        return jsonify({'error': 'Failed to create intent'}), 500

@integrations_bp.route('/whatsapp/phone-numbers/<phone_number_id>/profile', methods=['GET'])
@jwt_required()
def get_whatsapp_business_profile(phone_number_id):
    """Get WhatsApp business profile"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find chatbot by phone number ID
        chatbot = Chatbot.query.filter_by(whatsapp_phone_number_id=phone_number_id).first()
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get business profile from WhatsApp
        profile = whatsapp_service.get_business_profile(phone_number_id)
        
        return jsonify({
            'profile': profile
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get WhatsApp profile error: {str(e)}")
        return jsonify({'error': 'Failed to get business profile'}), 500

@integrations_bp.route('/whatsapp/phone-numbers/<phone_number_id>/profile', methods=['PUT'])
@jwt_required()
def update_whatsapp_business_profile(phone_number_id):
    """Update WhatsApp business profile"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find chatbot by phone number ID
        chatbot = Chatbot.query.filter_by(whatsapp_phone_number_id=phone_number_id).first()
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Update business profile in WhatsApp
        result = whatsapp_service.update_business_profile(phone_number_id, data)
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.INTEGRATION_UPDATED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'integration_type': 'whatsapp',
                'phone_number_id': phone_number_id,
                'profile_data': data
            }
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Business profile updated successfully',
            'result': result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Update WhatsApp profile error: {str(e)}")
        return jsonify({'error': 'Failed to update business profile'}), 500

@integrations_bp.route('/whatsapp/send-message', methods=['POST'])
@jwt_required()
def send_whatsapp_message():
    """Send WhatsApp message manually"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        chatbot_id = data.get('chatbot_id')
        to = data.get('to')
        message_type = data.get('type', 'text')
        content = data.get('content')
        
        if not all([chatbot_id, to, content]):
            return jsonify({'error': 'chatbot_id, to, and content are required'}), 400
        
        chatbot = Chatbot.find_by_id(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        if not chatbot.whatsapp_phone_number_id:
            return jsonify({'error': 'WhatsApp not configured for this chatbot'}), 400
        
        # Format phone number
        formatted_phone = whatsapp_service.format_phone_number(to)
        if not whatsapp_service.validate_phone_number(formatted_phone):
            return jsonify({'error': 'Invalid phone number format'}), 400
        
        # Send message based on type
        if message_type == 'text':
            result = whatsapp_service.send_text_message(
                chatbot.whatsapp_phone_number_id,
                formatted_phone,
                content
            )
        elif message_type == 'template':
            template_name = data.get('template_name')
            language_code = data.get('language_code', 'en')
            parameters = data.get('parameters', [])
            
            if not template_name:
                return jsonify({'error': 'template_name is required for template messages'}), 400
            
            result = whatsapp_service.send_template_message(
                chatbot.whatsapp_phone_number_id,
                formatted_phone,
                template_name,
                language_code,
                parameters
            )
        else:
            return jsonify({'error': 'Unsupported message type'}), 400
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.MESSAGE_SENT,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'message_type': message_type,
                'recipient': formatted_phone,
                'manual_send': True
            }
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Message sent successfully',
            'result': result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Send WhatsApp message error: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500

@integrations_bp.route('/test-connection', methods=['POST'])
@jwt_required()
def test_integration_connection():
    """Test connection to external services"""
    try:
        data = request.get_json()
        service = data.get('service')  # 'botpress' or 'whatsapp'
        
        if service == 'botpress':
            # Test Botpress connection
            try:
                bots = botpress_service.list_bots()
                return jsonify({
                    'service': 'botpress',
                    'status': 'connected',
                    'message': f'Successfully connected to Botpress. Found {len(bots)} bots.',
                    'bots_count': len(bots)
                }), 200
            except Exception as e:
                return jsonify({
                    'service': 'botpress',
                    'status': 'error',
                    'message': f'Failed to connect to Botpress: {str(e)}'
                }), 500
        
        elif service == 'whatsapp':
            # Test WhatsApp connection
            phone_number_id = data.get('phone_number_id')
            if not phone_number_id:
                return jsonify({'error': 'phone_number_id is required for WhatsApp test'}), 400
            
            try:
                phone_info = whatsapp_service.get_phone_number_info(phone_number_id)
                return jsonify({
                    'service': 'whatsapp',
                    'status': 'connected',
                    'message': 'Successfully connected to WhatsApp Business API',
                    'phone_info': phone_info
                }), 200
            except Exception as e:
                return jsonify({
                    'service': 'whatsapp',
                    'status': 'error',
                    'message': f'Failed to connect to WhatsApp: {str(e)}'
                }), 500
        
        else:
            return jsonify({'error': 'Invalid service. Use "botpress" or "whatsapp"'}), 400
        
    except Exception as e:
        current_app.logger.error(f"Test integration connection error: {str(e)}")
        return jsonify({'error': 'Failed to test connection'}), 500

