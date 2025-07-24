from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import json
import hmac
import hashlib

from src.models import db
from src.models.webhook import WebhookEvent
from src.models.chatbot import Chatbot
from src.models.conversation import Conversation, Message
from src.models.analytics import AnalyticsEvent, AnalyticsEventTypes
from src.services.botpress_service import botpress_service
from src.services.whatsapp_service import whatsapp_service

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/whatsapp', methods=['GET'])
def verify_whatsapp_webhook():
    """Verify WhatsApp webhook subscription"""
    try:
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        current_app.logger.info(f"WhatsApp webhook verification: mode={mode}, token={token}")
        
        result = whatsapp_service.verify_webhook(mode, token, challenge)
        if result:
            return result, 200
        else:
            return 'Verification failed', 403
            
    except Exception as e:
        current_app.logger.error(f"WhatsApp webhook verification error: {str(e)}")
        return 'Verification failed', 403

@webhooks_bp.route('/whatsapp', methods=['POST'])
def handle_whatsapp_webhook():
    """Handle incoming WhatsApp webhook events"""
    try:
        webhook_data = request.get_json()
        current_app.logger.info(f"Received WhatsApp webhook: {json.dumps(webhook_data, indent=2)}")
        
        # Process webhook events
        events = whatsapp_service.process_webhook_event(webhook_data)
        
        for event in events:
            # Store webhook event
            webhook_event = WebhookEvent(
                source='whatsapp',
                event_type=event['type'],
                event_data=event,
                phone_number_id=event.get('phone_number_id'),
                processed=False
            )
            db.session.add(webhook_event)
            
            # Process different event types
            if event['type'] == 'message_received':
                await_process_whatsapp_message(event, webhook_event.id)
            elif event['type'] == 'message_status':
                await_process_whatsapp_status(event, webhook_event.id)
        
        db.session.commit()
        return jsonify({'status': 'success', 'processed_events': len(events)}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"WhatsApp webhook processing error: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def await_process_whatsapp_message(event, webhook_event_id):
    """Process incoming WhatsApp message"""
    try:
        phone_number_id = event.get('phone_number_id')
        customer_phone = event.get('from')
        message_content = event.get('content', {})
        message_type = event.get('message_type', 'text')
        
        # Find chatbot by phone number
        chatbot = Chatbot.query.filter_by(
            whatsapp_phone_number_id=phone_number_id,
            status='active'
        ).first()
        
        if not chatbot:
            current_app.logger.warning(f"No active chatbot found for phone number ID: {phone_number_id}")
            return
        
        # Find or create conversation
        conversation = Conversation.query.filter_by(
            chatbot_id=chatbot.id,
            customer_phone=customer_phone,
            status='open'
        ).first()
        
        if not conversation:
            conversation = Conversation(
                chatbot_id=chatbot.id,
                customer_phone=customer_phone,
                customer_name=customer_phone,  # Will be updated if available
                status='open',
                started_at=datetime.utcnow(),
                last_message_at=datetime.utcnow()
            )
            db.session.add(conversation)
            db.session.flush()  # Get conversation ID
            
            # Track conversation started event
            AnalyticsEvent.track_event(
                company_id=chatbot.company_id,
                event_name=AnalyticsEventTypes.CONVERSATION_STARTED,
                chatbot_id=chatbot.id,
                event_data={
                    'conversation_id': conversation.id,
                    'customer_phone': customer_phone,
                    'channel': 'whatsapp'
                }
            )
        
        # Create message record
        message_data = {
            'direction': 'inbound',
            'type': message_type,
            'content': message_content.get('text', '') if message_type == 'text' else json.dumps(message_content),
            'sender_phone': customer_phone,
            'sender_name': customer_phone,
            'whatsapp_message_id': event.get('message_id'),
            'media_url': message_content.get('media_id') if message_type != 'text' else None,
            'media_type': message_content.get('mime_type') if message_type != 'text' else None,
            'message_metadata': {
                'webhook_event_id': webhook_event_id,
                'phone_number_id': phone_number_id,
                'raw_event': event
            }
        }
        
        message = conversation.add_message(message_data)
        
        # Track message received event
        AnalyticsEvent.track_event(
            company_id=chatbot.company_id,
            event_name=AnalyticsEventTypes.MESSAGE_RECEIVED,
            chatbot_id=chatbot.id,
            event_data={
                'conversation_id': conversation.id,
                'message_id': message.id,
                'message_type': message_type,
                'customer_phone': customer_phone
            }
        )
        
        # Forward message to Botpress if configured
        if chatbot.botpress_bot_id and chatbot.auto_response_enabled:
            try:
                # Create or get Botpress conversation
                botpress_conversation = botpress_service.create_conversation(
                    chatbot.botpress_bot_id,
                    customer_phone,
                    'whatsapp'
                )
                
                # Send message to Botpress
                botpress_message = {
                    'type': 'text',
                    'text': message_content.get('text', '') if message_type == 'text' else f"[{message_type.upper()}] message received",
                    'userId': customer_phone
                }
                
                botpress_service.send_message(
                    chatbot.botpress_bot_id,
                    botpress_conversation.get('conversation', {}).get('id'),
                    botpress_message
                )
                
            except Exception as e:
                current_app.logger.error(f"Failed to forward message to Botpress: {str(e)}")
        
        # Mark WhatsApp message as read
        try:
            whatsapp_service.mark_message_as_read(phone_number_id, event.get('message_id'))
        except Exception as e:
            current_app.logger.error(f"Failed to mark message as read: {str(e)}")
        
        # Update webhook event as processed
        webhook_event = WebhookEvent.query.get(webhook_event_id)
        if webhook_event:
            webhook_event.processed = True
            webhook_event.processed_at = datetime.utcnow()
        
        current_app.logger.info(f"Processed WhatsApp message for conversation {conversation.id}")
        
    except Exception as e:
        current_app.logger.error(f"Failed to process WhatsApp message: {str(e)}")
        raise

def await_process_whatsapp_status(event, webhook_event_id):
    """Process WhatsApp message status update"""
    try:
        message_id = event.get('message_id')
        status = event.get('status')
        
        # Find message by WhatsApp message ID
        message = Message.query.filter_by(whatsapp_message_id=message_id).first()
        
        if message:
            # Update message status
            if status == 'sent':
                message.mark_delivered()
            elif status == 'delivered':
                message.mark_delivered()
            elif status == 'read':
                message.mark_read()
            elif status == 'failed':
                message.mark_failed(event.get('error', {}).get('message', 'Unknown error'))
            
            current_app.logger.info(f"Updated message {message_id} status to {status}")
        
        # Update webhook event as processed
        webhook_event = WebhookEvent.query.get(webhook_event_id)
        if webhook_event:
            webhook_event.processed = True
            webhook_event.processed_at = datetime.utcnow()
        
    except Exception as e:
        current_app.logger.error(f"Failed to process WhatsApp status: {str(e)}")
        raise

@webhooks_bp.route('/botpress', methods=['POST'])
def handle_botpress_webhook():
    """Handle incoming Botpress webhook events"""
    try:
        webhook_data = request.get_json()
        current_app.logger.info(f"Received Botpress webhook: {json.dumps(webhook_data, indent=2)}")
        
        # Validate webhook signature if configured
        signature = request.headers.get('X-Botpress-Signature')
        if signature:
            webhook_secret = current_app.config.get('BOTPRESS_WEBHOOK_SECRET')
            if webhook_secret:
                payload = request.get_data(as_text=True)
                if not botpress_service.validate_webhook_signature(payload, signature, webhook_secret):
                    current_app.logger.warning("Invalid Botpress webhook signature")
                    return jsonify({'error': 'Invalid signature'}), 403
        
        # Process webhook event
        processed_event = botpress_service.process_webhook_event(webhook_data)
        
        # Store webhook event
        webhook_event = WebhookEvent(
            source='botpress',
            event_type=processed_event['event_type'],
            event_data=processed_event,
            bot_id=processed_event.get('bot_id'),
            processed=False
        )
        db.session.add(webhook_event)
        db.session.flush()
        
        # Process different event types
        if processed_event['event_type'] == 'message_received':
            await_process_botpress_message(processed_event, webhook_event.id)
        elif processed_event['event_type'] == 'conversation_started':
            await_process_botpress_conversation_started(processed_event, webhook_event.id)
        elif processed_event['event_type'] == 'conversation_ended':
            await_process_botpress_conversation_ended(processed_event, webhook_event.id)
        
        db.session.commit()
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Botpress webhook processing error: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def await_process_botpress_message(event, webhook_event_id):
    """Process incoming Botpress message (bot response)"""
    try:
        bot_id = event.get('bot_id')
        conversation_id = event.get('conversation_id')
        message_data = event.get('data', {})
        
        # Find chatbot by Botpress bot ID
        chatbot = Chatbot.query.filter_by(
            botpress_bot_id=bot_id,
            status='active'
        ).first()
        
        if not chatbot:
            current_app.logger.warning(f"No active chatbot found for Botpress bot ID: {bot_id}")
            return
        
        # Extract message content
        message_text = message_data.get('payload', {}).get('text', '')
        user_id = message_data.get('userId', '')
        
        if not message_text or not user_id:
            current_app.logger.warning("Invalid Botpress message data")
            return
        
        # Find conversation by customer phone
        conversation = Conversation.query.filter_by(
            chatbot_id=chatbot.id,
            customer_phone=user_id,
            status='open'
        ).first()
        
        if not conversation:
            current_app.logger.warning(f"No open conversation found for customer {user_id}")
            return
        
        # Send response via WhatsApp
        if chatbot.whatsapp_phone_number_id:
            try:
                whatsapp_response = whatsapp_service.send_text_message(
                    chatbot.whatsapp_phone_number_id,
                    user_id,
                    message_text
                )
                
                # Create message record
                message_record_data = {
                    'direction': 'outbound',
                    'type': 'text',
                    'content': message_text,
                    'sender_phone': chatbot.whatsapp_phone_number,
                    'sender_name': chatbot.name,
                    'whatsapp_message_id': whatsapp_response.get('messages', [{}])[0].get('id'),
                    'message_metadata': {
                        'webhook_event_id': webhook_event_id,
                        'botpress_conversation_id': conversation_id,
                        'bot_response': True
                    }
                }
                
                message = conversation.add_message(message_record_data)
                
                # Track message sent event
                AnalyticsEvent.track_event(
                    company_id=chatbot.company_id,
                    event_name=AnalyticsEventTypes.MESSAGE_SENT,
                    chatbot_id=chatbot.id,
                    event_data={
                        'conversation_id': conversation.id,
                        'message_id': message.id,
                        'message_type': 'text',
                        'customer_phone': user_id,
                        'bot_response': True
                    }
                )
                
                current_app.logger.info(f"Sent Botpress response to WhatsApp for conversation {conversation.id}")
                
            except Exception as e:
                current_app.logger.error(f"Failed to send WhatsApp response: {str(e)}")
        
        # Update webhook event as processed
        webhook_event = WebhookEvent.query.get(webhook_event_id)
        if webhook_event:
            webhook_event.processed = True
            webhook_event.processed_at = datetime.utcnow()
        
    except Exception as e:
        current_app.logger.error(f"Failed to process Botpress message: {str(e)}")
        raise

def await_process_botpress_conversation_started(event, webhook_event_id):
    """Process Botpress conversation started event"""
    try:
        # Update webhook event as processed
        webhook_event = WebhookEvent.query.get(webhook_event_id)
        if webhook_event:
            webhook_event.processed = True
            webhook_event.processed_at = datetime.utcnow()
        
        current_app.logger.info("Processed Botpress conversation started event")
        
    except Exception as e:
        current_app.logger.error(f"Failed to process Botpress conversation started: {str(e)}")
        raise

def await_process_botpress_conversation_ended(event, webhook_event_id):
    """Process Botpress conversation ended event"""
    try:
        # Update webhook event as processed
        webhook_event = WebhookEvent.query.get(webhook_event_id)
        if webhook_event:
            webhook_event.processed = True
            webhook_event.processed_at = datetime.utcnow()
        
        current_app.logger.info("Processed Botpress conversation ended event")
        
    except Exception as e:
        current_app.logger.error(f"Failed to process Botpress conversation ended: {str(e)}")
        raise

@webhooks_bp.route('/test', methods=['POST'])
def test_webhook():
    """Test webhook endpoint for development"""
    try:
        data = request.get_json()
        current_app.logger.info(f"Test webhook received: {json.dumps(data, indent=2)}")
        
        return jsonify({
            'status': 'success',
            'message': 'Test webhook received',
            'data': data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Test webhook error: {str(e)}")
        return jsonify({'error': 'Test webhook failed'}), 500

@webhooks_bp.route('/events', methods=['GET'])
def get_webhook_events():
    """Get recent webhook events for debugging"""
    try:
        limit = request.args.get('limit', 50, type=int)
        source = request.args.get('source')  # 'whatsapp' or 'botpress'
        
        query = WebhookEvent.query
        
        if source:
            query = query.filter_by(source=source)
        
        events = query.order_by(WebhookEvent.created_at.desc()).limit(limit).all()
        
        events_data = [
            {
                'id': event.id,
                'source': event.source,
                'event_type': event.event_type,
                'processed': event.processed,
                'created_at': event.created_at.isoformat(),
                'processed_at': event.processed_at.isoformat() if event.processed_at else None,
                'event_data': event.event_data
            }
            for event in events
        ]
        
        return jsonify({
            'events': events_data,
            'total': len(events_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get webhook events error: {str(e)}")
        return jsonify({'error': 'Failed to get webhook events'}), 500

