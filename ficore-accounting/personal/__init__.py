from flask import Blueprint, jsonify, current_app, redirect, url_for, flash, render_template, request, session
from flask_login import current_user, login_required
from utils import requires_role, is_admin, get_mongo_db
from translations import trans
from datetime import datetime
from bson import ObjectId

# Create the personal blueprint
personal_bp = Blueprint('personal', __name__, url_prefix='/personal', template_folder='templates')

def check_personal_access():
    """Check if user has access to personal finance tools"""
    return current_user.is_authenticated and (current_user.role == 'personal' or is_admin())

# Import all personal finance routes
from .bill import bill_bp
from .budget import budget_bp
from .emergency_fund import emergency_fund_bp
from .financial_health import financial_health_bp
from .learning_hub import learning_hub_bp
from .net_worth import net_worth_bp
from .quiz import quiz_bp

# Register all personal finance sub-blueprints
personal_bp.register_blueprint(bill_bp)
personal_bp.register_blueprint(budget_bp)
personal_bp.register_blueprint(emergency_fund_bp)
personal_bp.register_blueprint(financial_health_bp)
personal_bp.register_blueprint(learning_hub_bp)
personal_bp.register_blueprint(net_worth_bp)
personal_bp.register_blueprint(quiz_bp)

@personal_bp.before_request
def check_access():
    """Ensure only personal users and admins can access personal finance tools"""
    if not check_personal_access():
        flash(trans('general_access_denied', default='Access denied. Personal finance tools are only available to personal users.'), 'danger')
        return redirect(url_for('dashboard.index'))

@personal_bp.route('/notification_count')
@login_required
def notification_count():
    """Return the count of unread notifications for the current user"""
    try:
        with current_app.app_context():
            db = current_app.config['MONGO_CLIENT']['ficodb']
            user_id = current_user.id
            count = db.reminder_logs.count_documents({
                'user_id': user_id,
                'read_status': False
            })
            return jsonify({'count': count})
    except Exception as e:
        current_app.logger.error(f"Error fetching notification count: {str(e)}")
        return jsonify({'error': 'Failed to fetch notification count'}), 500

@personal_bp.route('/notifications')
@login_required
def notifications():
    """Return the list of recent notifications for the current user"""
    try:
        with current_app.app_context():
            db = current_app.config['MONGO_CLIENT']['ficodb']
            user_id = current_user.id
            notifications = list(db.reminder_logs.find({
                'user_id': user_id
            }).sort('sent_at', -1).limit(10))
            notification_ids = [n['notification_id'] for n in notifications if not n.get('read_status', False)]
            if notification_ids:
                db.reminder_logs.update_many(
                    {'notification_id': {'$in': notification_ids}},
                    {'$set': {'read_status': True}}
                )
            result = [{
                'id': str(n['notification_id']),
                'message': n['message'],
                'type': n['type'],
                'timestamp': n['sent_at'].isoformat(),
                'read': n.get('read_status', False)
            } for n in notifications]
            return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching notifications: {str(e)}")
        return jsonify({'error': 'Failed to fetch notifications'}), 500

@personal_bp.route('/index')
def index():
    """Render the personal index page"""
    lang = session.get('lang', 'en')
    try:
        return render_template(
            'personal/GENERAL/index.html',
            t=trans,
            lang=lang,
            title=trans('general_welcome', lang=lang)
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering personal index: {str(e)}")
        return render_template(
            'personal/GENERAL/error.html',
            t=trans,
            lang=lang,
            error=str(e),
            title=trans('general_error', lang=lang)
        ), 500

@personal_bp.route('/general_dashboard')
def general_dashboard():
    """Redirect to the unified dashboard"""
    return redirect(url_for('dashboard.index'))

# NEW: Added recent_activity endpoint for homepage
@personal_bp.route('/recent_activity')
@login_required
def recent_activity():
    """Return recent activity across all personal finance tools for the current user."""
    try:
        db = get_mongo_db()
        user_id = current_user.id
        activities = []

        # Fetch recent bills
        bills = db.bills.find({'user_id': user_id}).sort('created_at', -1).limit(5)
        for bill in bills:
            activities.append({
                'type': 'bill',
                'description': trans('recent_activity_bill_added', default='Added bill: {name}', lang=session.get('lang', 'en'), name=bill['bill_name']),
                'timestamp': bill['created_at'].isoformat(),
                'details': {
                    'amount': bill['amount'],
                    'due_date': bill['due_date'],
                    'status': bill['status']
                }
            })

        # Fetch recent budgets
        budgets = db.budgets.find({'user_id': user_id}).sort('created_at', -1).limit(5)
        for budget in budgets:
            activities.append({
                'type': 'budget',
                'description': trans('recent_activity_budget_created', default='Created budget with income: {amount}', lang=session.get('lang', 'en'), amount=budget['income']),
                'timestamp': budget['created_at'].isoformat(),
                'details': {
                    'income': budget['income'],
                    'surplus_deficit': budget['surplus_deficit']
                }
            })

        # Fetch recent net worth records
        net_worths = db.net_worth_data.find({'user_id': user_id}).sort('created_at', -1).limit(5)
        for nw in net_worths:
            activities.append({
                'type': 'net_worth',
                'description': trans('recent_activity_net_worth_calculated', default='Calculated net worth: {amount}', lang=session.get('lang', 'en'), amount=nw['net_worth']),
                'timestamp': nw['created_at'].isoformat(),
                'details': {
                    'net_worth': nw['net_worth'],
                    'total_assets': nw['total_assets'],
                    'total_liabilities': nw['total_liabilities']
                }
            })

        # Fetch recent financial health scores
        health_scores = db.financial_health_scores.find({'user_id': user_id}).sort('created_at', -1).limit(5)
        for hs in health_scores:
            activities.append({
                'type': 'financial_health',
                'description': trans('recent_activity_health_score', default='Calculated financial health score: {score}', lang=session.get('lang', 'en'), score=hs['score']),
                'timestamp': hs['created_at'].isoformat(),
                'details': {
                    'score': hs['score'],
                    'status': hs['status']
                }
            })

        # Sort all activities by timestamp and limit to 10
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:10]

        current_app.logger.info(f"Fetched {len(activities)} recent activities for user {user_id}", 
                              extra={'session_id': session.get('sid', 'unknown')})
        return jsonify(activities)
    except Exception as e:
        current_app.logger.error(f"Error in personal.recent_activity: {str(e)}", 
                                extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': 'Failed to fetch recent activity'}), 500

# Set language blueprint
set_language_bp = Blueprint('set_language', __name__)

@set_language_bp.route('/set_language/<lang>')
def set_language(lang):
    valid_langs = ['en', 'ha']
    new_lang = lang if lang in valid_langs else 'en'
    try:
        session['lang'] = new_lang
        with current_app.app_context():
            if current_user.is_authenticated:
                db = current_app.config['MONGO_CLIENT']['ficodb']
                db.users.update_one({'_id': current_user.id}, {'$set': {'language': new_lang}})
        current_app.logger.info(f"Language set to {new_lang}")
        flash(trans('general_language_changed', default='Language updated successfully'), 'success')
    except Exception as e:
        current_app.logger.error(f"Session operation failed: {str(e)}")
        flash(trans('general_invalid_language', default='Invalid language'), 'danger')
    return redirect(request.referrer or url_for('personal.index'))

# Notifications blueprint (optional, as it’s redundant with personal_bp)
notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/notification_count')
@login_required
def notification_count():
    try:
        db = get_mongo_db()
        user_id = current_user.id
        count = db.reminder_logs.count_documents({
            'user_id': user_id,
            'read_status': False
        })
        return jsonify({'count': count})
    except Exception as e:
        current_app.logger.error(f"Error fetching notification count: {str(e)}")
        return jsonify({'error': 'Failed to fetch notification count'}), 500

@notifications_bp.route('/notifications')
@login_required
def notifications():
    try:
        db = get_mongo_db()
        user_id = current_user.id
        notifications = list(db.reminder_logs.find({
            'user_id': user_id
        }).sort('sent_at', -1).limit(10))
        notification_ids = [n['notification_id'] for n in notifications if not n.get('read_status', False)]
        if notification_ids:
            db.reminder_logs.update_many(
                {'notification_id': {'$in': notification_ids}},
                {'$set': {'read_status': True}}
            )
        result = [{
            'id': str(n['notification_id']),
            'message': n['message'],
            'type': n['type'],
            'timestamp': n['sent_at'].isoformat(),
            'read': n.get('read_status', False)
        } for n in notifications]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching notifications: {str(e)}")
        return jsonify({'error': 'Failed to fetch notifications'}), 500

# Export the blueprints
__all__ = ['personal_bp', 'set_language_bp', 'notifications_bp']
