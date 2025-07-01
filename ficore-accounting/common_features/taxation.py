from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField, StringField, DateField
from wtforms.validators import DataRequired, NumberRange
from translations import trans
from utils import requires_role, get_mongo_db
import logging

taxation_bp = Blueprint('taxation_bp', __name__, template_folder='templates')

class TaxCalculationForm(FlaskForm):
    amount = FloatField(trans('tax_amount', default='Amount'), validators=[DataRequired(), NumberRange(min=0, message='Amount must be non-negative')])
    submit = SubmitField(trans('tax_calculate', default='Calculate Tax'))

class ReminderForm(FlaskForm):
    message = StringField(trans('tax_reminder_message', default='Reminder Message'), validators=[DataRequired()])
    reminder_date = DateField(trans('tax_reminder_date', default='Reminder Date'), validators=[DataRequired()])
    submit = SubmitField(trans('tax_add_reminder', default='Add Reminder'))

class TaxRateForm(FlaskForm):
    role = StringField(trans('tax_role', default='Role'), validators=[DataRequired()])
    min_income = FloatField(trans('tax_min_income', default='Minimum Income'), validators=[DataRequired(), NumberRange(min=0)])
    max_income = FloatField(trans('tax_max_income', default='Maximum Income'), validators=[DataRequired(), NumberRange(min=0)])
    rate = FloatField(trans('tax_rate', default='Tax Rate'), validators=[DataRequired(), NumberRange(min=0, max=1)])
    description = StringField(trans('tax_description', default='Description'), validators=[DataRequired()])
    submit = SubmitField(trans('tax_submit_rate', default='Submit Tax Rate'))

@taxation_bp.route('/calculate', methods=['GET', 'POST'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def calculate_tax():
    form = TaxCalculationForm()
    db = get_mongo_db()
    tax_rates = list(db.tax_rates.find({'role': current_user.role}))  # Fetch rates for user's role
    if request.method == 'POST':
        if form.validate_on_submit():
            amount = form.amount.data
            logging.info(f"POST /calculate: user={current_user.username}, amount={amount}, role={current_user.role}")
            tax_rate = db.tax_rates.find_one({'role': current_user.role, 'min_income': {'$lte': amount}, 'max_income': {'$gte': amount}})
            if tax_rate:
                tax = amount * tax_rate['rate']
                explanation = tax_rate['description']
                logging.info(f"Tax calculated: tax={tax}, explanation={explanation}")
                if request.is_json:
                    return jsonify({'tax': tax, 'explanation': explanation, 'amount': amount})
                return render_template('common_features/taxation/taxation.html', 
                                     section='result', 
                                     tax=tax, 
                                     explanation=explanation, 
                                     amount=amount, 
                                     form=form, 
                                     tax_rates=tax_rates,
                                     t=trans, 
                                     lang=session.get('lang', 'en'))
            else:
                logging.warning(f"No tax rate found for role={current_user.role}, amount={amount}")
                flash(trans('tax_no_rate_found', default='No tax rate found for your role and amount'), 'warning')
        else:
            logging.error(f"Form validation failed: {form.errors}")
            flash(trans('tax_invalid_input', default='Invalid input. Please check your amount.'), 'danger')
        if request.is_json:
            return jsonify({'error': trans('tax_invalid_input', default='Invalid input')}), 400
    return render_template('common_features/taxation/taxation.html', 
                         section='calculate', 
                         form=form, 
                         role=current_user.role, 
                         tax_rates=tax_rates,
                         t=trans, 
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/payment-info')
@requires_role(['personal', 'trader', 'agent'])
@login_required
def payment_info():
    db = get_mongo_db()
    locations = list(db.payment_locations.find())
    return render_template('common_features/taxation/taxation.html', 
                         section='payment_info', 
                         locations=locations, 
                         t=trans, 
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/reminders', methods=['GET', 'POST'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def reminders():
    db = get_mongo_db()
    form = ReminderForm()
    if form.validate_on_submit():
        db.tax_reminders.insert_one({
            'user_id': current_user.id,
            'message': form.message.data,
            'reminder_date': form.reminder_date.data,
            'created_at': datetime.datetime.utcnow()
        })
        flash(trans('tax_reminder_added', default='Reminder added successfully'), 'success')
        return redirect(url_for('taxation_bp.reminders'))
    reminders = list(db.tax_reminders.find({'user_id': current_user.id}))
    return render_template('common_features/taxation/taxation.html', 
                         section='reminders', 
                         reminders=reminders, 
                         form=form,
                         t=trans, 
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/admin/rates', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_tax_rates():
    form = TaxRateForm()
    db = get_mongo_db()
    if form.validate_on_submit():
        db.tax_rates.insert_one({
            'role': form.role.data,
            'min_income': form.min_income.data,
            'max_income': form.max_income.data,
            'rate': form.rate.data,
            'description': form.description.data
        })
        flash(trans('tax_rate_added', default='Tax rate added successfully'), 'success')
        return redirect(url_for('taxation_bp.manage_tax_rates'))
    rates = list(db.tax_rates.find())
    return render_template('common_features/taxation/taxation.html', 
                         section='admin_rates', 
                         form=form, 
                         rates=rates,
                         t=trans, 
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/admin/locations', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_payment_locations():
    # Simple implementation for adding locations
    form = FlaskForm()  # Reuse a basic form for simplicity
    db = get_mongo_db()
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact = request.form.get('contact')
        if name and address and contact:
            db.payment_locations.insert_one({'name': name, 'address': address, 'contact': contact})
            flash(trans('tax_location_added', default='Payment location added successfully'), 'success')
            return redirect(url_for('taxation_bp.manage_payment_locations'))
        flash(trans('tax_invalid_input', default='Invalid input'), 'danger')
    locations = list(db.payment_locations.find())
    return render_template('common_features/taxation/taxation.html', 
                         section='admin_locations', 
                         locations=locations,
                         t=trans, 
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/admin/deadlines', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_tax_deadlines():
    # Simple implementation for adding deadlines
    form = FlaskForm()
    db = get_mongo_db()
    if request.method == 'POST':
        deadline_date = request.form.get('deadline_date')
        description = request.form.get('description')
        if deadline_date and description:
            db.tax_deadlines.insert_one({'deadline_date': deadline_date, 'description': description})
            flash(trans('tax_deadline_added', default='Tax deadline added successfully'), 'success')
            return redirect(url_for('taxation_bp.manage_tax_deadlines'))
        flash(trans('tax_invalid_input', default='Invalid input'), 'danger')
    deadlines = list(db.tax_deadlines.find())
    return render_template('common_features/taxation/taxation.html', 
                         section='admin_deadlines', 
                         deadlines=deadlines,
                         t=trans, 
                         lang=session.get('lang', 'en'))
