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
from personal.bill import bill_bp
from personal.budget import budget_bp
from personal.emergency_fund import emergency_fund_bp
from personal.financial_health import financial_health_bp
from personal.learning_hub import learning_hub_bp
from personal.net_worth import net_worth_bp
from personal.quiz import quiz_bp

# Register all personal finance sub-blueprints
personal_bp.register_blueprint(bill_bp)
personal_bp.register_blueprint(budget_bp)
personal_bp.register_blueprint(emergency_fund_bp)
personal_bp.register_blueprint(financial_health_bp)
personal_bp.register_blueprint(learning_hub_bp)
personal_bp.register_blueprint(net_worth_bp)
personal_bp.register_blueprint(quiz_bp)

@personal_bp.route('/index')
def index():
    """Render the personal index page for both authenticated and anonymous users"""
    lang = session.get('lang', 'en')
    try:
        courses = current_app.config.get('COURSES', [])
        return render_template(
            'personal/GENERAL/index.html',
            t=trans,
            lang=lang,
            courses=courses,
            is_anonymous=session.get('is_anonymous', not current_user.is_authenticated),
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

@personal_bp.route('/notification_count')
@login_required
def notification_count():
    """Return the count of unread notifications for the current user"""
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

@personal_bp.route('/notifications')
@login_required
def notifications():
    """Return the list of recent notifications for the current user"""
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

@personal_bp.route('/')
@login_required
def index():
    if current_user.role not in ['personal', 'admin']:
        return redirect(url_for('app.index'))
    tools = PERSONAL_TOOLS if current_user.role == 'personal' else ALL_TOOLS
    nav_items = PERSONAL Healthy diet plan_NAV if current_user.role == 'personal' else ADMIN_NAV
    return render_template('personal/GENERAL/index.html', tools=tools, nav_items=nav_items, t=trans, lang=session.get('lang', 'en'))

@personal_bp.route('/recent_activity')
@login_required
def recent_activity():
    """Return recent activity across all personal finance tools for the current user"""
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
                    'due_date': bill['due_date'].isoformat(),
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

        # Fetch recent emergency fund plans
        emergency_funds = db.emergency_funds.find({'user_id': user_id}).sort('created_at', -1).limit(5)
        for ef in emergency_funds:
            activities.append({
                'type': 'emergency_fund',
                'description': trans('recent_activity_emergency_fund_created', default='Created emergency fund plan with target: {amount}', lang=session.get('lang', 'en'), amount=ef['target_amount']),
                'timestamp': ef['created_at'].isoformat(),
                'details': {
                    'target_amount': ef['target_amount'],
                    'savings_gap': ef['savings_gap'],
                    'monthly_savings': ef['monthly_savings']
                }
            })

        # Fetch recent quiz results
        quizzes = db.quiz_responses.find({'user_id': user_id}).sort('created_at', -1).limit(5)
        for quiz in quizzes:
            activities.append({
                'type': 'quiz',
                'description': trans('recent_activity_quiz_completed', default='Completed financial quiz with score: {score}', lang=session.get('lang', 'en'), score=quiz['score']),
                'timestamp': quiz['created_at'].isoformat(),
                'details': {
                    'score': quiz['score'],
                    'personality': quiz['personality']
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
