import requests
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    """Service for integrating with WhatsApp Business API"""
    
    def __init__(self):
        self.api_url = os.environ.get('WHATSAPP_API_URL', 'https://graph.facebook.com/v18.0')
        self.access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN')
        self.verify_token = os.environ.get('WHATSAPP_VERIFY_TOKEN')
        
        if not self.access_token:
            logger.warning("WHATSAPP_ACCESS_TOKEN not configured")
        
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to WhatsApp API"""
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
            logger.error(f"WhatsApp API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise Exception(f"WhatsApp API error: {str(e)}")
    
    def send_text_message(self, phone_number_id: str, to: str, message: str) -> Dict:
        """Send a text message"""
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {
                "body": message
            }
        }
        
        try:
            result = self._make_request('POST', f'/{phone_number_id}/messages', data)
            logger.info(f"Sent text message to {to}")
            return result
        except Exception as e:
            logger.error(f"Failed to send text message: {str(e)}")
            raise
    
    def send_template_message(self, phone_number_id: str, to: str, template_name: str, language_code: str = "en", parameters: List[str] = None) -> Dict:
        """Send a template message"""
        template_data = {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
        
        if parameters:
            template_data["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in parameters]
                }
            ]
        
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template_data
        }
        
        try:
            result = self._make_request('POST', f'/{phone_number_id}/messages', data)
            logger.info(f"Sent template message {template_name} to {to}")
            return result
        except Exception as e:
            logger.error(f"Failed to send template message: {str(e)}")
            raise
    
    def send_media_message(self, phone_number_id: str, to: str, media_type: str, media_url: str, caption: str = None) -> Dict:
        """Send a media message (image, video, audio, document)"""
        media_data = {
            "link": media_url
        }
        
        if caption and media_type in ['image', 'video']:
            media_data["caption"] = caption
        
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: media_data
        }
        
        try:
            result = self._make_request('POST', f'/{phone_number_id}/messages', data)
            logger.info(f"Sent {media_type} message to {to}")
            return result
        except Exception as e:
            logger.error(f"Failed to send media message: {str(e)}")
            raise
    
    def send_interactive_message(self, phone_number_id: str, to: str, interactive_data: Dict) -> Dict:
        """Send an interactive message (buttons, list, etc.)"""
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive_data
        }
        
        try:
            result = self._make_request('POST', f'/{phone_number_id}/messages', data)
            logger.info(f"Sent interactive message to {to}")
            return result
        except Exception as e:
            logger.error(f"Failed to send interactive message: {str(e)}")
            raise
    
    def send_button_message(self, phone_number_id: str, to: str, text: str, buttons: List[Dict]) -> Dict:
        """Send a message with buttons"""
        interactive_data = {
            "type": "button",
            "body": {
                "text": text
            },
            "action": {
                "buttons": buttons
            }
        }
        
        return self.send_interactive_message(phone_number_id, to, interactive_data)
    
    def send_list_message(self, phone_number_id: str, to: str, text: str, button_text: str, sections: List[Dict]) -> Dict:
        """Send a message with a list"""
        interactive_data = {
            "type": "list",
            "body": {
                "text": text
            },
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
        
        return self.send_interactive_message(phone_number_id, to, interactive_data)
    
    def mark_message_as_read(self, phone_number_id: str, message_id: str) -> Dict:
        """Mark a message as read"""
        data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            result = self._make_request('POST', f'/{phone_number_id}/messages', data)
            logger.info(f"Marked message {message_id} as read")
            return result
        except Exception as e:
            logger.error(f"Failed to mark message as read: {str(e)}")
            raise
    
    def get_media(self, media_id: str) -> Dict:
        """Get media object details"""
        try:
            result = self._make_request('GET', f'/{media_id}')
            return result
        except Exception as e:
            logger.error(f"Failed to get media {media_id}: {str(e)}")
            raise
    
    def download_media(self, media_url: str) -> bytes:
        """Download media content"""
        try:
            response = requests.get(media_url, headers=self.headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download media: {str(e)}")
            raise
    
    def get_phone_number_info(self, phone_number_id: str) -> Dict:
        """Get phone number information"""
        try:
            result = self._make_request('GET', f'/{phone_number_id}')
            return result
        except Exception as e:
            logger.error(f"Failed to get phone number info: {str(e)}")
            raise
    
    def get_business_profile(self, phone_number_id: str) -> Dict:
        """Get business profile information"""
        try:
            result = self._make_request('GET', f'/{phone_number_id}/whatsapp_business_profile')
            return result
        except Exception as e:
            logger.error(f"Failed to get business profile: {str(e)}")
            raise
    
    def update_business_profile(self, phone_number_id: str, profile_data: Dict) -> Dict:
        """Update business profile"""
        data = {
            "messaging_product": "whatsapp",
            **profile_data
        }
        
        try:
            result = self._make_request('POST', f'/{phone_number_id}/whatsapp_business_profile', data)
            logger.info(f"Updated business profile for {phone_number_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update business profile: {str(e)}")
            raise
    
    def create_message_template(self, business_account_id: str, template_data: Dict) -> Dict:
        """Create a message template"""
        try:
            result = self._make_request('POST', f'/{business_account_id}/message_templates', template_data)
            logger.info(f"Created message template: {template_data.get('name')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create message template: {str(e)}")
            raise
    
    def get_message_templates(self, business_account_id: str) -> List[Dict]:
        """Get all message templates"""
        try:
            result = self._make_request('GET', f'/{business_account_id}/message_templates')
            return result.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get message templates: {str(e)}")
            raise
    
    def delete_message_template(self, business_account_id: str, template_name: str) -> Dict:
        """Delete a message template"""
        params = {"name": template_name}
        
        try:
            result = self._make_request('DELETE', f'/{business_account_id}/message_templates', params)
            logger.info(f"Deleted message template: {template_name}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete message template: {str(e)}")
            raise
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """Verify webhook subscription"""
        if mode == "subscribe" and token == self.verify_token:
            logger.info("Webhook verified successfully")
            return challenge
        else:
            logger.warning("Webhook verification failed")
            return None
    
    def process_webhook_event(self, webhook_data: Dict) -> List[Dict]:
        """Process incoming webhook event from WhatsApp"""
        processed_events = []
        
        try:
            entry = webhook_data.get('entry', [])
            
            for entry_item in entry:
                changes = entry_item.get('changes', [])
                
                for change in changes:
                    if change.get('field') == 'messages':
                        value = change.get('value', {})
                        
                        # Process messages
                        messages = value.get('messages', [])
                        for message in messages:
                            event = {
                                'type': 'message_received',
                                'message_id': message.get('id'),
                                'from': message.get('from'),
                                'timestamp': message.get('timestamp'),
                                'message_type': message.get('type'),
                                'content': self._extract_message_content(message),
                                'phone_number_id': value.get('metadata', {}).get('phone_number_id'),
                                'display_phone_number': value.get('metadata', {}).get('display_phone_number'),
                                'raw_data': message
                            }
                            processed_events.append(event)
                        
                        # Process statuses
                        statuses = value.get('statuses', [])
                        for status in statuses:
                            event = {
                                'type': 'message_status',
                                'message_id': status.get('id'),
                                'recipient_id': status.get('recipient_id'),
                                'status': status.get('status'),
                                'timestamp': status.get('timestamp'),
                                'phone_number_id': value.get('metadata', {}).get('phone_number_id'),
                                'raw_data': status
                            }
                            processed_events.append(event)
            
            logger.info(f"Processed {len(processed_events)} webhook events")
            return processed_events
            
        except Exception as e:
            logger.error(f"Failed to process webhook event: {str(e)}")
            raise
    
    def _extract_message_content(self, message: Dict) -> Dict:
        """Extract content from message based on type"""
        message_type = message.get('type')
        content = {}
        
        if message_type == 'text':
            content = {'text': message.get('text', {}).get('body', '')}
        elif message_type == 'image':
            image_data = message.get('image', {})
            content = {
                'media_id': image_data.get('id'),
                'mime_type': image_data.get('mime_type'),
                'sha256': image_data.get('sha256'),
                'caption': image_data.get('caption', '')
            }
        elif message_type == 'video':
            video_data = message.get('video', {})
            content = {
                'media_id': video_data.get('id'),
                'mime_type': video_data.get('mime_type'),
                'sha256': video_data.get('sha256'),
                'caption': video_data.get('caption', '')
            }
        elif message_type == 'audio':
            audio_data = message.get('audio', {})
            content = {
                'media_id': audio_data.get('id'),
                'mime_type': audio_data.get('mime_type'),
                'sha256': audio_data.get('sha256')
            }
        elif message_type == 'document':
            document_data = message.get('document', {})
            content = {
                'media_id': document_data.get('id'),
                'mime_type': document_data.get('mime_type'),
                'sha256': document_data.get('sha256'),
                'filename': document_data.get('filename', ''),
                'caption': document_data.get('caption', '')
            }
        elif message_type == 'location':
            location_data = message.get('location', {})
            content = {
                'latitude': location_data.get('latitude'),
                'longitude': location_data.get('longitude'),
                'name': location_data.get('name', ''),
                'address': location_data.get('address', '')
            }
        elif message_type == 'contacts':
            content = {'contacts': message.get('contacts', [])}
        elif message_type == 'interactive':
            interactive_data = message.get('interactive', {})
            content = {
                'type': interactive_data.get('type'),
                'button_reply': interactive_data.get('button_reply'),
                'list_reply': interactive_data.get('list_reply')
            }
        
        return content
    
    def format_phone_number(self, phone_number: str) -> str:
        """Format phone number for WhatsApp API"""
        # Remove all non-digit characters
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        # Add country code if missing (assuming Kazakhstan +7)
        if len(cleaned) == 10 and cleaned.startswith('7'):
            return cleaned
        elif len(cleaned) == 10:
            return f"7{cleaned}"
        elif len(cleaned) == 11 and cleaned.startswith('8'):
            return f"7{cleaned[1:]}"
        
        return cleaned
    
    def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format"""
        formatted = self.format_phone_number(phone_number)
        return len(formatted) >= 10 and formatted.isdigit()

# Global instance
whatsapp_service = WhatsAppService()

