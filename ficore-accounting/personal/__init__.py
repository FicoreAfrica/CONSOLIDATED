from flask import Blueprint, jsonify, current_app, redirect, url_for, flash, render_template, request, session
from flask_login import current_user, login_required
from utils import requires_role, is_admin, get_mongo_db, PERSONAL_TOOLS, PERSONAL_NAV, ALL_TOOLS, ADMIN_NAV, limiter
from translations import trans
from datetime import datetime
from bson import ObjectId

personal_bp = Blueprint('personal', __name__, url_prefix='/personal', template_folder='templates/personal')

# Register all personal finance sub-blueprints
from personal.bill import bill_bp
from personal.budget import budget_bp
from personal.emergency_fund import emergency_fund_bp
from personal.financial_health import financial_health_bp
from personal.learning_hub import learning_hub_bp
from personal.net_worth import net_worth_bp
from personal.quiz import quiz_bp

personal_bp.register_blueprint(bill_bp)
personal_bp.register_blueprint(budget_bp)
personal_bp.register_blueprint(emergency_fund_bp)
personal_bp.register_blueprint(financial_health_bp)
personal_bp.register_blueprint(learning_hub_bp)
personal_bp.register_blueprint(net_worth_bp)
personal_bp.register_blueprint(quiz_bp)

def init_app(app):
    """Initialize all personal finance sub-blueprints."""
    try:
        # Initialize each sub-blueprint
        for blueprint in [bill_bp, budget_bp, emergency_fund_bp, financial_health_bp, learning_hub_bp, net_worth_bp, quiz_bp]:
            if hasattr(blueprint, 'init_app'):
                blueprint.init_app(app)
                current_app.logger.info(f"Initialized {blueprint.name} blueprint", extra={'session_id': 'no-request-context'})
        current_app.logger.info("Personal finance blueprints initialized successfully", extra={'session_id': 'no-request-context'})
    except Exception as e:
        current_app.logger.error(f"Error initializing personal finance blueprints: {str(e)}", extra={'session_id': 'no-request-context'})
        raise

@personal_bp.route('/')
@login_required
@requires_role(['personal', 'admin'])
def index():
    """Render the personal finance dashboard."""
    try:
        tools = PERSONAL_TOOLS if current_user.role == 'personal' else ALL_TOOLS
        # Use bottom_nav_items for consistency in passing navigation data to templates
        bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else ADMIN_NAV
        return render_template(
            'personal/GENERAL/index.html',
            tools=tools,
            bottom_nav_items=bottom_nav_items,  # Updated to use bottom_nav_items
            t=trans,
            lang=session.get('lang', 'en'),
            title=trans('general_welcome', default='Welcome')
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering personal index: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('general_error', default='An error occurred'), 'danger')
        tools = PERSONAL_TOOLS if current_user.role == 'personal' else ALL_TOOLS
        # Use bottom_nav_items in error case for consistency
        bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else ADMIN_NAV
        return render_template(
            'personal/GENERAL/index.html',
            tools=tools,
            bottom_nav_items=bottom_nav_items,  # Updated to use bottom_nav_items
            t=trans,
            lang=session.get('lang', 'en'),
            title=trans('general_welcome', default='Welcome')
        ), 500

@personal_bp.route('/notification_count')
@login_required
@requires_role(['personal', 'admin'])
def notification_count():
    """Return the count of unread notifications for the current user."""
    try:
        db = get_mongo_db()
        query = {'read_status': False} if is_admin() else {'user_id': current_user.id, 'read_status': False}
        count = db.reminder_logs.count_documents(query)
        current_app.logger.info(f"Fetched notification count {count} for user {current_user.id}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'count': count})
    except Exception as e:
        current_app.logger.error(f"Error fetching notification count: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_something_went_wrong', default='Failed to fetch notification count')}), 500

@personal_bp.route('/notifications')
@login_required
@requires_role(['personal', 'admin'])
def notifications():
    """Return the list of recent notifications for the current user."""
    try:
        db = get_mongo_db()
        query = {} if is_admin() else {'user_id': current_user.id}
        notifications = list(db.reminder_logs.find(query).sort('sent_at', -1).limit(10))
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
        current_app.logger.info(f"Fetched {len(result)} notifications for user {current_user.id}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"2Error fetching notifications: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_something_went_wrong', default='Failed to fetch notifications')}), 500

@personal_bp.route('/recent_activity')
@login_required
@requires_role(['personal', 'admin'])
def recent_activity():
    """Return recent activity across all personal finance tools for the current user."""
    try:
        db = get_mongo_db()
        query = {} if is_admin() else {'user_id': current_user.id}
        activities = []

        # Fetch recent bills
        bills = db.bills.find(query).sort('created_at', -1).limit(5)
        for bill in bills:
            activities.append({
                'type': 'bill',
                'description': trans('recent_activity_bill_added', default='Added bill: {name}', name=bill['bill_name']),
                'timestamp': bill['created_at'].isoformat(),
                'details': {
                    'amount': bill['amount'],
                    'due_date': bill['due_date'],
                    'status': bill['status']
                }
            })

        # Fetch recent budgets
        budgets = db.budgets.find(query).sort('created_at', -1).limit(5)
        for budget in budgets:
            activities.append({
                'type': 'budget',
                'description': trans('recent_activity_budget_created', default='Created budget with income: {amount}', amount=budget['income']),
                'timestamp': budget['created_at'].isoformat(),
                'details': {
                    'income': budget['income'],
                    'surplus_deficit': budget['surplus_deficit']
                }
            })

        # Fetch recent net worth records
        net_worths = db.net_worth_data.find(query).sort('created_at', -1).limit(5)
        for nw in net_worths:
            activities.append({
                'type': 'net_worth',
                'description': trans('recent_activity_net_worth_calculated', default='Calculated net worth: {amount}', amount=nw['net_worth']),
                'timestamp': nw['created_at'].isoformat(),
                'details': {
                    'net_worth': nw['net_worth'],
                    'total_assets': nw['total_assets'],
                    'total_liabilities': nw['total_liabilities']
                }
            })

        # Fetch recent financial health scores
        health_scores = db.financial_health_scores.find(query).sort('created_at', -1).limit(5)
        for hs in health_scores:
            activities.append({
                'type': 'financial_health',
                'description': trans('recent_activity_health_score', default='Calculated financial health score: {score}', score=hs['score']),
                'timestamp': hs['created_at'].isoformat(),
                'details': {
                    'score': hs['score'],
                    'status': hs['status']
                }
            })

        # Fetch recent emergency fund plans
        emergency_funds = db.emergency_funds.find(query).sort('created_at', -1).limit(5)
        for ef in emergency_funds:
            activities.append({
                'type': 'emergency_fund',
                'description': trans('recent_activity_emergency_fund_created', default='Created emergency fund plan with target: {amount}', amount=ef['target_amount']),
                'timestamp': ef['created_at'].isoformat(),
                'details': {
                    'target_amount': ef['target_amount'],
                    'savings_gap': ef['savings_gap'],
                    'monthly_savings': ef['monthly_savings']
                }
            })

        # Fetch recent quiz results
        quizzes = db.quiz_responses.find(query).sort('created_at', -1).limit(5)
        for quiz in quizzes:
            activities.append({
                'type': 'quiz',
                'description': trans('recent_activity_quiz_completed', default='Completed financial quiz with score: {score}', score=quiz['score']),
                'timestamp': quiz['created_at'].isoformat(),
                'details': {
                    'score': quiz['score'],
                    'personality': quiz['personality']
                }
            })

        # Fetch recent learning hub progress
        learning_hub_progress = db.learning_materials.find(query).sort('updated_at', -1).limit(5)
        for progress in learning_hub_progress:
            if progress.get('course_id'):
                activities.append({
                    'type': 'learning_hub',
                    'description': trans('recent_activity_learning_hub_progress', default='Progress in course: {course_id}', course_id=progress['course_id']),
                    'timestamp': progress['updated_at'].isoformat(),
                    'details': {
                        'course_id': progress['course_id'],
                        'lessons_completed': len(progress.get('lessons_completed', [])),
                        'current_lesson': progress.get('current_lesson', 'N/A')
                    }
                })

        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:10]
        current_app.logger.info(f"Fetched {len(activities)} recent activities for user {current_user.id}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify(activities)
    except Exception as e:
        current_app.logger.error(f"Error in personal.recent_activity: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_something_went_wrong', default='Failed to fetch recent activity')}), 500
