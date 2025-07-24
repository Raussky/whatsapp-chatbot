from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from src.models import db
from src.models.user import User
from src.models.chatbot import Chatbot
from src.models.conversation import Conversation, Message
from src.models.analytics import AnalyticsEvent, AnalyticsEventTypes

conversations_bp = Blueprint('conversations', __name__)

@conversations_bp.route('/<conversation_id>', methods=['GET'])
@jwt_required()
def get_conversation(conversation_id):
    """Get a specific conversation with messages"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access through chatbot
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        include_messages = request.args.get('include_messages', 'true').lower() == 'true'
        message_limit = request.args.get('message_limit', 50, type=int)
        message_offset = request.args.get('message_offset', 0, type=int)
        
        conversation_data = conversation.to_dict(include_messages=False)
        
        if include_messages:
            messages = Message.get_conversation_messages(
                conversation_id, 
                limit=message_limit, 
                offset=message_offset
            )
            conversation_data['messages'] = [msg.to_dict() for msg in reversed(messages)]
            conversation_data['message_pagination'] = {
                'limit': message_limit,
                'offset': message_offset,
                'total_messages': conversation.message_count
            }
        
        # Include chatbot info
        conversation_data['chatbot'] = {
            'id': chatbot.id,
            'name': chatbot.name,
            'company_id': chatbot.company_id
        }
        
        return jsonify({'conversation': conversation_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get conversation error: {str(e)}")
        return jsonify({'error': 'Failed to get conversation'}), 500

@conversations_bp.route('/<conversation_id>/messages', methods=['GET'])
@jwt_required()
def get_conversation_messages(conversation_id):
    """Get messages for a conversation with pagination"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Query messages with pagination
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        messages_data = [msg.to_dict() for msg in reversed(messages.items)]
        
        return jsonify({
            'messages': messages_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': messages.total,
                'pages': messages.pages,
                'has_next': messages.has_next,
                'has_prev': messages.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get conversation messages error: {str(e)}")
        return jsonify({'error': 'Failed to get messages'}), 500

@conversations_bp.route('/<conversation_id>/messages', methods=['POST'])
@jwt_required()
def send_message(conversation_id):
    """Send a message in a conversation"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('content'):
            return jsonify({'error': 'Message content is required'}), 400
        
        # Create message
        message_data = {
            'direction': 'outbound',
            'type': data.get('type', 'text'),
            'content': data['content'],
            'sender_phone': chatbot.whatsapp_phone_number,
            'sender_name': chatbot.name,
            'media_url': data.get('media_url'),
            'media_type': data.get('media_type'),
            'metadata': data.get('metadata', {})
        }
        
        message = conversation.add_message(message_data)
        db.session.commit()
        
        # TODO: Send message via WhatsApp API
        # send_whatsapp_message(chatbot, conversation.customer_phone, message_data)
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.MESSAGE_SENT,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'conversation_id': conversation_id,
                'message_type': message.type,
                'customer_phone': conversation.customer_phone
            }
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Message sent successfully',
            'message_data': message.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Send message error: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500

@conversations_bp.route('/<conversation_id>/close', methods=['POST'])
@jwt_required()
def close_conversation(conversation_id):
    """Close a conversation"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Close the conversation
        conversation.close()
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.CONVERSATION_ENDED,
            chatbot_id=chatbot.id,
            user_id=user_id,
            event_data={
                'conversation_id': conversation_id,
                'customer_phone': conversation.customer_phone,
                'duration_minutes': conversation.get_duration_minutes()
            }
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Conversation closed successfully',
            'conversation': conversation.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Close conversation error: {str(e)}")
        return jsonify({'error': 'Failed to close conversation'}), 500

@conversations_bp.route('/<conversation_id>/reopen', methods=['POST'])
@jwt_required()
def reopen_conversation(conversation_id):
    """Reopen a closed conversation"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Reopen the conversation
        conversation.reopen()
        db.session.commit()
        
        return jsonify({
            'message': 'Conversation reopened successfully',
            'conversation': conversation.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Reopen conversation error: {str(e)}")
        return jsonify({'error': 'Failed to reopen conversation'}), 500

@conversations_bp.route('/<conversation_id>/assign', methods=['POST'])
@jwt_required()
def assign_conversation(conversation_id):
    """Assign conversation to a user"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        assign_to_user_id = data.get('user_id')
        
        if assign_to_user_id:
            # Verify the user exists and has access to this company
            assign_to_user = User.find_by_id(assign_to_user_id)
            if not assign_to_user:
                return jsonify({'error': 'User to assign not found'}), 404
            
            assign_to_companies = [comp['company'].id for comp in assign_to_user.get_companies()]
            if chatbot.company_id not in assign_to_companies:
                return jsonify({'error': 'User does not have access to this company'}), 403
        
        # Assign the conversation
        conversation.assign_to_user(assign_to_user_id)
        db.session.commit()
        
        return jsonify({
            'message': 'Conversation assigned successfully',
            'conversation': conversation.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Assign conversation error: {str(e)}")
        return jsonify({'error': 'Failed to assign conversation'}), 500

@conversations_bp.route('/<conversation_id>/tags', methods=['POST'])
@jwt_required()
def add_conversation_tag(conversation_id):
    """Add a tag to a conversation"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        tag = data.get('tag', '').strip()
        
        if not tag:
            return jsonify({'error': 'Tag is required'}), 400
        
        # Add the tag
        conversation.add_tag(tag)
        db.session.commit()
        
        return jsonify({
            'message': 'Tag added successfully',
            'conversation': conversation.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Add conversation tag error: {str(e)}")
        return jsonify({'error': 'Failed to add tag'}), 500

@conversations_bp.route('/<conversation_id>/tags/<tag>', methods=['DELETE'])
@jwt_required()
def remove_conversation_tag(conversation_id, tag):
    """Remove a tag from a conversation"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Remove the tag
        conversation.remove_tag(tag)
        db.session.commit()
        
        return jsonify({
            'message': 'Tag removed successfully',
            'conversation': conversation.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Remove conversation tag error: {str(e)}")
        return jsonify({'error': 'Failed to remove tag'}), 500

@conversations_bp.route('/<conversation_id>/metadata', methods=['PUT'])
@jwt_required()
def update_conversation_metadata(conversation_id):
    """Update conversation metadata"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access
        chatbot = conversation.chatbot
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if chatbot.company_id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        metadata = data.get('metadata', {})
        
        # Update metadata
        conversation.update_metadata(metadata)
        db.session.commit()
        
        return jsonify({
            'message': 'Metadata updated successfully',
            'conversation': conversation.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update conversation metadata error: {str(e)}")
        return jsonify({'error': 'Failed to update metadata'}), 500

