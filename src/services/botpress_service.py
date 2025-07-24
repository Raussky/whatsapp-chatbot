import requests
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BotpressService:
    """Service for integrating with Botpress Cloud API"""
    
    def __init__(self):
        self.api_url = os.environ.get('BOTPRESS_API_URL', 'https://api.botpress.cloud')
        self.api_token = os.environ.get('BOTPRESS_API_TOKEN')
        self.workspace_id = os.environ.get('BOTPRESS_WORKSPACE_ID')
        
        if not self.api_token:
            logger.warning("BOTPRESS_API_TOKEN not configured")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to Botpress API"""
        url = f"{self.api_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, params=data)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Botpress API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise Exception(f"Botpress API error: {str(e)}")
    
    def create_bot(self, name: str, description: str = "", avatar_url: str = None) -> Dict:
        """Create a new bot in Botpress"""
        data = {
            'name': name,
            'description': description,
            'workspaceId': self.workspace_id
        }
        
        if avatar_url:
            data['avatarUrl'] = avatar_url
        
        try:
            result = self._make_request('POST', '/v1/bots', data)
            logger.info(f"Created bot: {name} with ID: {result.get('bot', {}).get('id')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create bot {name}: {str(e)}")
            raise
    
    def get_bot(self, bot_id: str) -> Dict:
        """Get bot details by ID"""
        try:
            result = self._make_request('GET', f'/v1/bots/{bot_id}')
            return result
        except Exception as e:
            logger.error(f"Failed to get bot {bot_id}: {str(e)}")
            raise
    
    def update_bot(self, bot_id: str, name: str = None, description: str = None, avatar_url: str = None) -> Dict:
        """Update bot configuration"""
        data = {}
        if name:
            data['name'] = name
        if description:
            data['description'] = description
        if avatar_url:
            data['avatarUrl'] = avatar_url
        
        try:
            result = self._make_request('PUT', f'/v1/bots/{bot_id}', data)
            logger.info(f"Updated bot: {bot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update bot {bot_id}: {str(e)}")
            raise
    
    def delete_bot(self, bot_id: str) -> bool:
        """Delete a bot"""
        try:
            self._make_request('DELETE', f'/v1/bots/{bot_id}')
            logger.info(f"Deleted bot: {bot_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete bot {bot_id}: {str(e)}")
            raise
    
    def list_bots(self) -> List[Dict]:
        """List all bots in workspace"""
        try:
            result = self._make_request('GET', f'/v1/workspaces/{self.workspace_id}/bots')
            return result.get('bots', [])
        except Exception as e:
            logger.error(f"Failed to list bots: {str(e)}")
            raise
    
    def create_conversation(self, bot_id: str, user_id: str, channel: str = 'whatsapp') -> Dict:
        """Create a new conversation"""
        data = {
            'userId': user_id,
            'channel': channel
        }
        
        try:
            result = self._make_request('POST', f'/v1/bots/{bot_id}/conversations', data)
            logger.info(f"Created conversation for bot {bot_id} and user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to create conversation: {str(e)}")
            raise
    
    def send_message(self, bot_id: str, conversation_id: str, message: Dict) -> Dict:
        """Send a message in a conversation"""
        try:
            result = self._make_request('POST', f'/v1/bots/{bot_id}/conversations/{conversation_id}/messages', message)
            logger.info(f"Sent message in conversation {conversation_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            raise
    
    def get_conversation_messages(self, bot_id: str, conversation_id: str, limit: int = 50) -> List[Dict]:
        """Get messages from a conversation"""
        params = {'limit': limit}
        
        try:
            result = self._make_request('GET', f'/v1/bots/{bot_id}/conversations/{conversation_id}/messages', params)
            return result.get('messages', [])
        except Exception as e:
            logger.error(f"Failed to get conversation messages: {str(e)}")
            raise
    
    def create_webhook(self, bot_id: str, webhook_url: str, events: List[str] = None) -> Dict:
        """Create a webhook for bot events"""
        if events is None:
            events = ['message_received', 'conversation_started', 'conversation_ended']
        
        data = {
            'url': webhook_url,
            'events': events,
            'enabled': True
        }
        
        try:
            result = self._make_request('POST', f'/v1/bots/{bot_id}/webhooks', data)
            logger.info(f"Created webhook for bot {bot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to create webhook: {str(e)}")
            raise
    
    def update_webhook(self, bot_id: str, webhook_id: str, webhook_url: str = None, events: List[str] = None, enabled: bool = None) -> Dict:
        """Update webhook configuration"""
        data = {}
        if webhook_url:
            data['url'] = webhook_url
        if events:
            data['events'] = events
        if enabled is not None:
            data['enabled'] = enabled
        
        try:
            result = self._make_request('PUT', f'/v1/bots/{bot_id}/webhooks/{webhook_id}', data)
            logger.info(f"Updated webhook {webhook_id} for bot {bot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update webhook: {str(e)}")
            raise
    
    def get_bot_analytics(self, bot_id: str, start_date: str = None, end_date: str = None) -> Dict:
        """Get analytics data for a bot"""
        params = {}
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date
        
        try:
            result = self._make_request('GET', f'/v1/bots/{bot_id}/analytics', params)
            return result
        except Exception as e:
            logger.error(f"Failed to get bot analytics: {str(e)}")
            raise
    
    def create_intent(self, bot_id: str, name: str, utterances: List[str], responses: List[str]) -> Dict:
        """Create a new intent for the bot"""
        data = {
            'name': name,
            'utterances': utterances,
            'responses': responses
        }
        
        try:
            result = self._make_request('POST', f'/v1/bots/{bot_id}/intents', data)
            logger.info(f"Created intent {name} for bot {bot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to create intent: {str(e)}")
            raise
    
    def update_intent(self, bot_id: str, intent_id: str, name: str = None, utterances: List[str] = None, responses: List[str] = None) -> Dict:
        """Update an existing intent"""
        data = {}
        if name:
            data['name'] = name
        if utterances:
            data['utterances'] = utterances
        if responses:
            data['responses'] = responses
        
        try:
            result = self._make_request('PUT', f'/v1/bots/{bot_id}/intents/{intent_id}', data)
            logger.info(f"Updated intent {intent_id} for bot {bot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update intent: {str(e)}")
            raise
    
    def train_bot(self, bot_id: str) -> Dict:
        """Train the bot with current intents and entities"""
        try:
            result = self._make_request('POST', f'/v1/bots/{bot_id}/train')
            logger.info(f"Started training for bot {bot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to train bot: {str(e)}")
            raise
    
    def get_training_status(self, bot_id: str) -> Dict:
        """Get training status for a bot"""
        try:
            result = self._make_request('GET', f'/v1/bots/{bot_id}/training-status')
            return result
        except Exception as e:
            logger.error(f"Failed to get training status: {str(e)}")
            raise
    
    def deploy_bot(self, bot_id: str) -> Dict:
        """Deploy the bot to production"""
        try:
            result = self._make_request('POST', f'/v1/bots/{bot_id}/deploy')
            logger.info(f"Deployed bot {bot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to deploy bot: {str(e)}")
            raise
    
    def validate_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Validate webhook signature for security"""
        import hmac
        import hashlib
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, f"sha256={expected_signature}")
    
    def process_webhook_event(self, event_data: Dict) -> Dict:
        """Process incoming webhook event from Botpress"""
        event_type = event_data.get('type')
        bot_id = event_data.get('botId')
        conversation_id = event_data.get('conversationId')
        
        logger.info(f"Processing webhook event: {event_type} for bot {bot_id}")
        
        # Return processed event data
        return {
            'event_type': event_type,
            'bot_id': bot_id,
            'conversation_id': conversation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'processed': True,
            'data': event_data
        }

# Global instance
botpress_service = BotpressService()

