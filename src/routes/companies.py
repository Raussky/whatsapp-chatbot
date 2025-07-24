from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from src.models import db
from src.models.user import User
from src.models.company import Company
from src.models.subscription import Subscription, SubscriptionPlan
from src.models.analytics import AnalyticsEvent, AnalyticsEventTypes

companies_bp = Blueprint('companies', __name__)

@companies_bp.route('/', methods=['GET'])
@jwt_required()
def get_companies():
    """Get companies for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user's companies
        companies = user.get_companies()
        
        companies_data = []
        for comp_info in companies:
            company_data = comp_info['company'].to_dict(include_relationships=True)
            company_data['user_role'] = comp_info['role']
            company_data['user_permissions'] = comp_info['permissions']
            companies_data.append(company_data)
        
        return jsonify({
            'companies': companies_data,
            'total': len(companies_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get companies error: {str(e)}")
        return jsonify({'error': 'Failed to get companies'}), 500

@companies_bp.route('/', methods=['POST'])
@jwt_required()
def create_company():
    """Create a new company"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'business_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create company
        company = Company(
            name=data['name'].strip(),
            business_type=data['business_type'].strip(),
            owner_id=user_id,
            description=data.get('description', '').strip(),
            website=data.get('website', '').strip(),
            phone=data.get('phone', '').strip(),
            email=data.get('email', '').strip(),
            address=data.get('address', '').strip(),
            city=data.get('city', '').strip(),
            country=data.get('country', 'Kazakhstan'),
            timezone=data.get('timezone', 'Asia/Almaty')
        )
        
        db.session.add(company)
        db.session.flush()  # Get company ID
        
        # Create default subscription (trial)
        starter_plan = SubscriptionPlan.find_by_type('starter')
        if starter_plan:
            subscription = Subscription(
                company_id=company.id,
                plan_id=starter_plan.id,
                status='trialing'
            )
            db.session.add(subscription)
        
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=company.id,
            event_name=AnalyticsEventTypes.COMPANY_CREATED,
            user_id=user_id,
            event_data={
                'company_name': company.name,
                'business_type': company.business_type
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Company created successfully',
            'company': company.to_dict(include_relationships=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create company error: {str(e)}")
        return jsonify({'error': 'Failed to create company'}), 500

@companies_bp.route('/<company_id>', methods=['GET'])
@jwt_required()
def get_company(company_id):
    """Get a specific company"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Check if user has access to this company
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company.id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get user's role in this company
        user_role = 'owner' if company.owner_id == user_id else 'member'
        
        company_data = company.to_dict(include_relationships=True)
        company_data['user_role'] = user_role
        
        # Include team members
        team_members = company.get_team_members()
        company_data['team_members'] = [
            {
                'user': member['user'].to_dict(),
                'role': member['role'],
                'permissions': member['permissions'],
                'joined_at': member['joined_at'].isoformat()
            }
            for member in team_members
        ]
        
        # Include usage statistics
        usage_stats = company.get_usage_stats()
        company_data['usage_stats'] = usage_stats
        
        return jsonify({'company': company_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get company error: {str(e)}")
        return jsonify({'error': 'Failed to get company'}), 500

@companies_bp.route('/<company_id>', methods=['PUT'])
@jwt_required()
def update_company(company_id):
    """Update a company"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Check if user is owner or has permission
        if company.owner_id != user_id:
            # Check if user has edit permission
            if not user.has_permission('edit_company', company_id):
                return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Update allowed fields
        allowed_fields = [
            'name', 'business_type', 'description', 'website', 
            'phone', 'email', 'address', 'city', 'country', 
            'timezone', 'logo_url'
        ]
        
        for field in allowed_fields:
            if field in data:
                setattr(company, field, data[field])
        
        company.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Track analytics event
        AnalyticsEvent.track_event(
            company_id=company.id,
            event_name=AnalyticsEventTypes.COMPANY_UPDATED,
            user_id=user_id,
            event_data={
                'company_name': company.name,
                'updated_fields': list(data.keys())
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        return jsonify({
            'message': 'Company updated successfully',
            'company': company.to_dict(include_relationships=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update company error: {str(e)}")
        return jsonify({'error': 'Failed to update company'}), 500

@companies_bp.route('/<company_id>', methods=['DELETE'])
@jwt_required()
def delete_company(company_id):
    """Delete a company (soft delete)"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Only owner can delete company
        if company.owner_id != user_id:
            return jsonify({'error': 'Only company owner can delete the company'}), 403
        
        # Soft delete the company
        company.soft_delete()
        db.session.commit()
        
        return jsonify({'message': 'Company deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete company error: {str(e)}")
        return jsonify({'error': 'Failed to delete company'}), 500

@companies_bp.route('/<company_id>/stats', methods=['GET'])
@jwt_required()
def get_company_stats(company_id):
    """Get company statistics"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company.id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        
        # Get usage statistics
        usage_stats = company.get_usage_stats()
        
        # Get chatbot statistics
        chatbots = company.get_active_chatbots()
        chatbot_stats = []
        
        for chatbot in chatbots:
            stats = chatbot.get_stats(days=days)
            chatbot_stats.append({
                'chatbot_id': chatbot.id,
                'chatbot_name': chatbot.name,
                **stats
            })
        
        # Get subscription info
        subscription = company.get_current_subscription()
        subscription_info = subscription.to_dict() if subscription else None
        
        return jsonify({
            'company_id': company_id,
            'usage_stats': usage_stats,
            'chatbot_stats': chatbot_stats,
            'subscription': subscription_info,
            'stats_period_days': days
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get company stats error: {str(e)}")
        return jsonify({'error': 'Failed to get company statistics'}), 500

@companies_bp.route('/<company_id>/team', methods=['GET'])
@jwt_required()
def get_team_members(company_id):
    """Get company team members"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Check access
        user_companies = [comp['company'].id for comp in user.get_companies()]
        if company.id not in user_companies:
            return jsonify({'error': 'Access denied'}), 403
        
        team_members = company.get_team_members()
        
        members_data = [
            {
                'user': member['user'].to_dict(),
                'role': member['role'],
                'permissions': member['permissions'],
                'joined_at': member['joined_at'].isoformat()
            }
            for member in team_members
        ]
        
        return jsonify({
            'team_members': members_data,
            'total': len(members_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get team members error: {str(e)}")
        return jsonify({'error': 'Failed to get team members'}), 500

@companies_bp.route('/<company_id>/invite', methods=['POST'])
@jwt_required()
def invite_team_member(company_id):
    """Invite a team member to the company"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        company = Company.find_by_id(company_id)
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Check if user can invite (owner or has permission)
        if company.owner_id != user_id and not user.has_permission('invite_users', company_id):
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        role = data.get('role', 'member')
        permissions = data.get('permissions', {})
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Check if user exists
        invited_user = User.find_by_email(email)
        if not invited_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is already a member
        from src.models.user import CompanyUser
        existing_membership = CompanyUser.query.filter_by(
            company_id=company_id,
            user_id=invited_user.id
        ).first()
        
        if existing_membership:
            return jsonify({'error': 'User is already a member of this company'}), 409
        
        # Create membership
        membership = CompanyUser(
            company_id=company_id,
            user_id=invited_user.id,
            role=role,
            permissions=permissions,
            invited_by=user_id,
            invited_at=datetime.utcnow()
        )
        
        db.session.add(membership)
        db.session.commit()
        
        # TODO: Send invitation email
        
        return jsonify({
            'message': 'Team member invited successfully',
            'membership': membership.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Invite team member error: {str(e)}")
        return jsonify({'error': 'Failed to invite team member'}), 500

