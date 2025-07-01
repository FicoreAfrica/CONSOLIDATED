from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, CSRFError
from wtforms import StringField, FloatField, SelectField, BooleanField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Email, Optional
from flask_login import current_user, login_required  # Added login_required
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime, date, timedelta
import uuid
from translations import trans
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from utils import requires_role, is_admin, get_mongo_db
from models import log_tool_usage
from session_utils import create_anonymous_session

bill_bp = Blueprint(
    'bill',
    __name__,
    template_folder='templates/personal/BILL',
    url_prefix='/bill'
)

# Initialize CSRF protection
csrf = CSRFProtect()

def strip_commas(value):
    """Remove commas from string values for numerical fields."""
    if isinstance(value, str):
        return value.replace(',', '')
    return value

def calculate_next_due_date(due_date, frequency):
    """Calculate the next due date based on frequency."""
    if frequency == 'weekly':
        return due_date + timedelta(days=7)
    elif frequency == 'monthly':
        return due_date + timedelta(days=30)
    elif frequency == 'quarterly':
        return due_date + timedelta(days=90)
    else:
        return due_date

def custom_login_required(f):
    """Custom login decorator that allows both authenticated users and anonymous sessions."""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated or session.get('is_anonymous', False):
            return f(*args, **kwargs)
        return redirect(url_for('users.login', next=request.url))
    return decorated_function

class BillForm(FlaskForm):
    first_name = StringField(trans('general_first_name', default='First Name'))
    email = StringField(trans('general_email', default='Email'))
    bill_name = StringField(trans('bill_bill_name', default='Bill Name'))
    amount = FloatField(trans('bill_amount', default='Amount'), filters=[strip_commas])
    due_date = StringField(trans('bill_due_date', default='Due Date (YYYY-MM-DD)'))
    frequency = SelectField(trans('bill_frequency', default='Frequency'), coerce=str)
    category = SelectField(trans('general_category', default='Category'), coerce=str)
    status = SelectField(trans('bill_status', default='Status'), coerce=str)
    send_email = BooleanField(trans('general_send_email', default='Send Email Reminders'))
    reminder_days = IntegerField(trans('bill_reminder_days', default='Reminder Days'), default=7)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        
        # Set up validators
        self.first_name.validators = [DataRequired(message=trans('general_first_name_required', lang))]
        self.email.validators = [DataRequired(message=trans('general_email_required', lang)), Email()]
        self.bill_name.validators = [DataRequired(message=trans('bill_bill_name_required', lang))]
        self.amount.validators = [DataRequired(message=trans('bill_amount_required', lang)), NumberRange(min=0, max=10000000000)]
        self.due_date.validators = [DataRequired(message=trans('bill_due_date_required', lang))]
        self.frequency.validators = [DataRequired(message=trans('bill_frequency_required', lang))]
        self.category.validators = [DataRequired(message=trans('bill_category_required', lang))]
        self.status.validators = [DataRequired(message=trans('bill_status_required', lang))]
        self.reminder_days.validators = [Optional(), NumberRange(min=1, max=30, message=trans('bill_reminder_days_required', lang))]

        # Set up choices
        self.frequency.choices = [
            ('one-time', trans('bill_frequency_one_time', lang)),
            ('weekly', trans('bill_frequency_weekly', lang)),
            ('monthly', trans('bill_frequency_monthly', lang)),
            ('quarterly', trans('bill_frequency_quarterly', lang))
        ]
        self.category.choices = [
            ('utilities', trans('bill_category_utilities', lang)),
            ('rent', trans('bill_category_rent', lang)),
            ('data_internet', trans('bill_category_data_internet', lang)),
            ('ajo_esusu_adashe', trans('bill_category_ajo_esusu_adashe', lang)),
            ('food', trans('bill_category_food', lang)),
            ('transport', trans('bill_category_transport', lang)),
            ('clothing', trans('bill_category_clothing', lang)),
            ('education', trans('bill_category_education', lang)),
            ('healthcare', trans('bill_category_healthcare', lang)),
            ('entertainment', trans('bill_category_entertainment', lang)),
            ('airtime', trans('bill_category_airtime', lang)),
            ('school_fees', trans('bill_category_school_fees', lang)),
            ('savings_investments', trans('bill_category_savings_investments', lang)),
            ('other', trans('general_other', lang))
        ]
        self.status.choices = [
            ('unpaid', trans('bill_status_unpaid', lang)),
            ('paid', trans('bill_status_paid', lang)),
            ('pending', trans('bill_status_pending', lang)),
            ('overdue', trans('bill_status_overdue', lang))
        ]

        # Set defaults
        self.frequency.default = self.frequency.choices[0][0]
        self.category.default = self.category.choices[0][0]
        self.status.default = self.status.choices[0][0]
        self.process()

class EditBillForm(FlaskForm):
    frequency = SelectField(trans('bill_frequency', default='Frequency'), coerce=str)
    category = SelectField(trans('general_category', default='Category'), coerce=str)
    status = SelectField(trans('bill_status', default='Status'), coerce=str)
    send_email = BooleanField(trans('general_send_email', default='Send Email Reminders'))
    reminder_days = IntegerField(trans('bill_reminder_days', default='Reminder Days'), default=7)

    def __init__(self, bill=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        
        # Set up validators
        self.frequency.validators = [DataRequired(message=trans('bill_frequency_required', lang))]
        self.category.validators = [DataRequired(message=trans('bill_category_required', lang))]
        self.status.validators = [DataRequired(message=trans('bill_status_required', lang))]
        self.reminder_days.validators = [Optional(), NumberRange(min=1, max=30, message=trans('bill_reminder_days_required', lang))]

        # Set up choices
        self.frequency.choices = [
            ('one-time', trans('bill_frequency_one_time', lang)),
            ('weekly', trans('bill_frequency_weekly', lang)),
            ('monthly', trans('bill_frequency_monthly', lang)),
            ('quarterly', trans('bill_frequency_quarterly', lang))
        ]
        self.category.choices = [
            ('utilities', trans('bill_category_utilities', lang)),
            ('rent', trans('bill_category_rent', lang)),
            ('data_internet', trans('bill_category_data_internet', lang)),
            ('ajo_esusu_adashe', trans('bill_category_ajo_esusu_adashe', lang)),
            ('food', trans('bill_category_food', lang)),
            ('transport', trans('bill_category_transport', lang)),
            ('clothing', trans('bill_category_clothing', lang)),
            ('education', trans('bill_category_education', lang)),
            ('healthcare', trans('bill_category_healthcare', lang)),
            ('entertainment', trans('bill_category_entertainment', lang)),
            ('airtime', trans('bill_category_airtime', lang)),
            ('school_fees', trans('bill_category_school_fees', lang)),
            ('savings_investments', trans('bill_category_savings_investments', lang)),
            ('other', trans('general_other', lang))
        ]
        self.status.choices = [
            ('unpaid', trans('bill_status_unpaid', lang)),
            ('paid', trans('bill_status_paid', lang)),
            ('pending', trans('bill_status_pending', lang)),
            ('overdue', trans('bill_status_overdue', lang))
        ]

        # Set defaults from bill data
        if bill:
            self.frequency.default = bill.get('frequency', self.frequency.choices[0][0])
            self.category.default = bill.get('category', self.category.choices[0][0])
            self.status.default = bill.get('status', self.status.choices[0][0])
            self.send_email.data = bill.get('send_email', False)
            self.reminder_days.data = bill.get('reminder_days', 7)
        self.process()

@bill_bp.route('/main', methods=['GET', 'POST'])
@custom_login_required
@requires_role(['personal', 'admin'])
def main():
    """Main bill management interface with tabbed layout."""
    if 'sid' not in session:
        create_anonymous_session()
        current_app.logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    
    # Initialize form with user data
    form_data = {}
    if current_user.is_authenticated:
        form_data['email'] = current_user.email
        form_data['first_name'] = current_user.username
    
    form = BillForm(data=form_data)
    
    log_tool_usage(
        get_mongo_db(),
        tool_name='bill',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='main_view'
    )

    tips = [
        trans('bill_tip_pay_early', default='Pay bills early to avoid penalties.', lang=lang),
        trans('bill_tip_energy_efficient', default='Use energy-efficient appliances to reduce utility bills.', lang=lang),
        trans('bill_tip_plan_monthly', default='Plan monthly expenses to manage cash flow.', lang=lang),
        trans('bill_tip_ajo_reminders', default='Set reminders for ajo contributions.', lang=lang),
        trans('bill_tip_data_topup', default='Schedule data top-ups to avoid service interruptions.', lang=lang)
    ]

    try:
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        bills_collection = get_mongo_db().bills
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'add_bill' and form.validate_on_submit():
                log_tool_usage(
                    get_mongo_db(),
                    tool_name='bill',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='add_bill'
                )
                
                try:
                    due_date = datetime.strptime(form.due_date.data, '%Y-%m-%d').date()
                    if due_date < date.today():
                        flash(trans('bill_due_date_future_validation', default='Due date must be today or in the future.', lang=lang), 'danger')
                        return redirect(url_for('bill.main'))
                except ValueError:
                    current_app.logger.error(f"Invalid due_date format: {form.due_date.data}", extra={'session_id': session['sid']})
                    flash(trans('bill_due_date_format_invalid', default='Invalid due date format.', lang=lang), 'danger')
                    return redirect(url_for('bill.main'))

                status = form.status.data
                if status not in ['paid', 'pending'] and due_date < date.today():
                    status = 'overdue'

                bill_data = {
                    '_id': ObjectId(),
                    'user_id': current_user.id if current_user.is_authenticated else None,
                    'session_id': session['sid'],
                    'user_email': form.email.data,
                    'first_name': form.first_name.data,
                    'bill_name': form.bill_name.data,
                    'amount': float(form.amount.data),
                    'due_date': due_date.isoformat(),
                    'frequency': form.frequency.data,
                    'category': form.category.data,
                    'status': status,
                    'send_email': form.send_email.data,
                    'reminder_days': form.reminder_days.data if form.send_email.data else None
                }

                bills_collection.insert_one(bill_data)
                current_app.logger.info(f"Bill added successfully for {form.email.data}: {bill_data['bill_name']}", extra={'session_id': session['sid']})
                flash(trans('bill_added_success', default='Bill added successfully!', lang=lang), 'success')

                # Send email if requested
                if form.send_email.data and form.email.data:
                    try:
                        config = EMAIL_CONFIG['bill_reminder']
                        subject = trans(config['subject_key'], default='Your Bill Reminder', lang=lang)
                        template = config['template']
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=form.email.data,
                            subject=subject,
                            template_name=template,
                            data={
                                'first_name': form.first_name.data,
                                'bills': [bill_data],
                                'cta_url': url_for('bill.main', _external=True),
                                'unsubscribe_url': url_for('bill.unsubscribe', email=form.email.data, _external=True)
                            },
                            lang=lang
                        )
                        current_app.logger.info(f"Email sent to {form.email.data}", extra={'session_id': session['sid']})
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email: {str(e)}", extra={'session_id': session['sid']})
                        flash(trans('general_email_send_failed', default='Failed to send email.', lang=lang), 'warning')

            elif action in ['update_bill', 'delete_bill', 'toggle_status']:
                bill_id = request.form.get('bill_id')
                bill = bills_collection.find_one({'_id': ObjectId(bill_id), **filter_kwargs})
                if not bill:
                    current_app.logger.warning(f"Bill {bill_id} not found for update/delete/toggle", extra={'session_id': session['sid']})
                    flash(trans('bill_not_found', default='Bill not found.', lang=lang), 'danger')
                    return redirect(url_for('bill.main'))

                if action == 'update_bill':
                    edit_form = EditBillForm(formdata=request.form, bill=bill)
                    if edit_form.validate():
                        update_data = {
                            'frequency': edit_form.frequency.data,
                            'category': edit_form.category.data,
                            'status': edit_form.status.data,
                            'send_email': edit_form.send_email.data,
                            'reminder_days': edit_form.reminder_days.data if edit_form.send_email.data else None
                        }
                        bills_collection.update_one({'_id': ObjectId(bill_id), **filter_kwargs}, {'$set': update_data})
                        current_app.logger.info(f"Bill {bill_id} updated successfully", extra={'session_id': session['sid']})
                        flash(trans('bill_updated_success', default='Bill updated successfully!', lang=lang), 'success')
                    else:
                        current_app.logger.error(f"Edit form validation failed: {edit_form.errors}", extra={'session_id': session['sid']})
                        flash(trans('bill_update_failed', default='Failed to update bill.', lang=lang), 'danger')

                elif action == 'delete_bill':
                    bills_collection.delete_one({'_id': ObjectId(bill_id), **filter_kwargs})
                    current_app.logger.info(f"Bill {bill_id} deleted successfully", extra={'session_id': session['sid']})
                    flash(trans('bill_deleted_success', default='Bill deleted successfully!', lang=lang), 'success')

                elif action == 'toggle_status':
                    new_status = 'paid' if bill['status'] == 'unpaid' else 'unpaid'
                    bills_collection.update_one({'_id': ObjectId(bill_id), **filter_kwargs}, {'$set': {'status': new_status}})
                    
                    # Create recurring bill if marked as paid and not one-time
                    if new_status == 'paid' and bill['frequency'] != 'one-time':
                        try:
                            due_date = datetime.strptime(bill['due_date'], '%Y-%m-%d').date()
                            new_due_date = calculate_next_due_date(due_date, bill['frequency'])
                            new_bill = bill.copy()
                            new_bill['_id'] = ObjectId()
                            new_bill['due_date'] = new_due_date.isoformat()
                            new_bill['status'] = 'unpaid'
                            bills_collection.insert_one(new_bill)
                            current_app.logger.info(f"Recurring bill created for {bill['bill_name']}", extra={'session_id': session['sid']})
                            flash(trans('bill_new_recurring_bill_success', default='New recurring bill created for {bill_name}.', lang=lang).format(bill_name=bill['bill_name']), 'success')
                        except Exception as e:
                            current_app.logger.error(f"Error creating recurring bill: {str(e)}", extra={'session_id': session['sid']})
                    
                    current_app.logger.info(f"Bill {bill_id} status toggled to {new_status}", extra={'session_id': session['sid']})
                    flash(trans('bill_status_toggled_success', default='Bill status toggled successfully!', lang=lang), 'success')

        # Get bills data for display
        bills = bills_collection.find(filter_kwargs)
        bills_data = []
        edit_forms = {}
        for bill in bills:
            bill_id = str(bill['_id'])
            try:
                bill['due_date'] = datetime.strptime(bill['due_date'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                current_app.logger.warning(f"Invalid due_date for bill {bill_id}: {bill.get('due_date')}", extra={'session_id': session['sid']})
                bill['due_date'] = date.today()
            edit_form = EditBillForm(bill=bill)
            bills_data.append((bill_id, bill, edit_form))
            edit_forms[bill_id] = edit_form

        # Calculate statistics
        paid_count = unpaid_count = overdue_count = pending_count = 0
        total_paid = total_unpaid = total_overdue = total_bills = 0.0
        categories = {}
        due_today = due_week = due_month = upcoming_bills = []

        today = date.today()
        for bill_id, bill, edit_form in bills_data:
            try:
                bill_amount = float(bill['amount'])
                total_bills += bill_amount
                cat = bill['category']
                categories[cat] = categories.get(cat, 0) + bill_amount

                if bill['status'] == 'paid':
                    paid_count += 1
                    total_paid += bill_amount
                elif bill['status'] == 'unpaid':
                    unpaid_count += 1
                    total_unpaid += bill_amount
                elif bill['status'] == 'overdue':
                    overdue_count += 1
                    total_overdue += bill_amount
                elif bill['status'] == 'pending':
                    pending_count += 1

                bill_due_date = bill['due_date']
                if bill_due_date == today:
                    due_today.append((bill_id, bill, edit_form))
                if today <= bill_due_date <= (today + timedelta(days=7)):
                    due_week.append((bill_id, bill, edit_form))
                if today <= bill_due_date <= (today + timedelta(days=30)):
                    due_month.append((bill_id, bill, edit_form))
                if today < bill_due_date:
                    upcoming_bills.append((bill_id, bill, edit_form))
            except (ValueError, TypeError):
                current_app.logger.warning(f"Invalid amount for bill {bill_id}: {bill.get('amount')}", extra={'session_id': session['sid']})
                continue

        return render_template(
            'bill_main.html',
            form=form,
            bills_data=bills_data,
            edit_forms=edit_forms,
            paid_count=paid_count,
            unpaid_count=unpaid_count,
            overdue_count=overdue_count,
            pending_count=pending_count,
            total_paid=total_paid,
            total_unpaid=total_unpaid,
            total_overdue=total_overdue,
            total_bills=total_bills,
            categories=categories,
            due_today=due_today,
            due_week=due_week,
            due_month=due_month,
            upcoming_bills=upcoming_bills,
            tips=tips,
            t=trans,
            lang=lang,
            tool_title=trans('bill_title', default='Bill Manager', lang=lang)
        )

    except Exception as e:
        current_app.logger.error(f"Error in bill.main: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('bill_dashboard_load_error', default='Error loading bill dashboard.', lang=lang), 'danger')
        return render_template(
            'bill_main.html',
            form=form,
            bills_data=[],
            edit_forms={},
            paid_count=0,
            unpaid_count=0,
            overdue_count=0,
            pending_count=0,
            total_paid=0.0,
            total_unpaid=0.0,
            total_overdue=0.0,
            total_bills=0.0,
            categories={},
            due_today=[],
            due_week=[],
            due_month=[],
            upcoming_bills=[],
            tips=tips,
            t=trans,
            lang=lang,
            tool_title=trans('bill_title', default='Bill Manager', lang=lang)
        ), 500

# NEW: Added summary endpoint for homepage financial summary
@bill_bp.route('/summary')
@login_required
def summary():
    """Return summary of upcoming bills for the current user."""
    try:
        filter_kwargs = {'user_id': current_user.id}
        bills_collection = get_mongo_db().bills
        today = date.today()
        
        # Aggregate total amount of upcoming bills (not paid, due in the future)
        pipeline = [
            {
                '$match': {
                    **filter_kwargs,
                    'status': {'$ne': 'paid'},
                    'due_date': {'$gte': today.isoformat()}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'totalUpcomingBills': {'$sum': '$amount'}
                }
            }
        ]
        result = list(bills_collection.aggregate(pipeline))
        total_upcoming_bills = result[0]['totalUpcomingBills'] if result else 0.0
        
        current_app.logger.info(f"Fetched bill summary for user {current_user.id}: {total_upcoming_bills}", 
                              extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'totalUpcomingBills': total_upcoming_bills})
    except Exception as e:
        current_app.logger.error(f"Error in bill.summary: {str(e)}", 
                                extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'totalUpcomingBills': 0.0}), 500

@bill_bp.route('/unsubscribe/<email>')
@custom_login_required
def unsubscribe(email):
    """Unsubscribe user from bill email notifications."""
    if 'sid' not in session:
        create_anonymous_session()
        current_app.logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            get_mongo_db(),
            tool_name='bill',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='unsubscribe'
        )
        filter_criteria = {'user_email': email}
        if current_user.is_authenticated:
            filter_criteria['user_id'] = current_user.id
        else:
            filter_criteria['session_id'] = session['sid']
        
        bills_collection = get_mongo_db().bills
        existing_record = bills_collection.find_one(filter_criteria)
        if not existing_record:
            current_app.logger.warning(f"No matching record found for email {email} to unsubscribe", extra={'session_id': session['sid']})
            flash(trans('bill_unsubscribe_failed', default='No matching email found or already unsubscribed.', lang=lang), 'danger')
            return redirect(url_for('personal.index'))

        result = bills_collection.update_many(
            filter_criteria,
            {'$set': {'send_email': False}}
        )
        if result.modified_count > 0:
            current_app.logger.info(f"Successfully unsubscribed email {email}", extra={'session_id': session['sid']})
            flash(trans('bill_unsubscribe_success', default='Successfully unsubscribed from bill emails.', lang=lang), 'success')
        else:
            current_app.logger.warning(f"No records updated for email {email} during unsubscribe", extra={'session_id': session['sid']})
            flash(trans('bill_unsubscribe_failed', default='No matching email found or already unsubscribed.', lang=lang), 'danger')
        session.permanent = True
        session.modified = True
        return redirect(url_for('personal.index'))
    except Exception as e:
        current_app.logger.error(f"Error in bill.unsubscribe: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('bill_unsubscribe_error', default='Error processing unsubscribe request.', lang=lang), 'danger')
        return redirect(url_for('personal.index'))

@bill_bp.errorhandler(CSRFError)
def handle_csrf_error(e):
    """Handle CSRF errors with user-friendly message."""
    lang = session.get('lang', 'en')
    current_app.logger.error(f"CSRF error on {request.path}: {e.description}", extra={'session_id': session.get('sid', 'unknown')})
    flash(trans('bill_csrf_error', default='Form submission failed due to a missing security token. Please refresh and try again.', lang=lang), 'danger')
    return redirect(url_for('bill.main')), 400
