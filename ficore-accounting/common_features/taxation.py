from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from translations import trans
from utils import requires_role, get_mongo_db
import logging
import datetime
from bson import ObjectId

taxation_bp = Blueprint('taxation_bp', __name__)

class TaxCalculationForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Calculate Tax')

class TaxRateForm(FlaskForm):
    role = SelectField('Role', choices=[('personal', 'Personal'), ('trader', 'Trader'), ('agent', 'Agent')], validators=[DataRequired()])
    min_income = FloatField('Minimum Income', validators=[DataRequired(), NumberRange(min=0)])
    max_income = FloatField('Maximum Income', validators=[DataRequired(), NumberRange(min=0)])
    rate = FloatField('Rate', validators=[DataRequired(), NumberRange(min=0, max=1)])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Add Tax Rate')

class ReminderForm(FlaskForm):
    message = StringField('Message', validators=[DataRequired()])
    reminder_date = DateField('Reminder Date', validators=[DataRequired()])
    submit = SubmitField('Add Reminder')

@taxation_bp.route('/calculate', methods=['GET', 'POST'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def calculate_tax():
    form = TaxCalculationForm()
    db = get_mongo_db()
    tax_rates = list(db.tax_rates.find({'role': current_user.role}))
    if request.method == 'POST':
        if form.validate_on_submit():
            amount = form.amount.data
            logging.info(f"POST /calculate: user={current_user.username}, amount={amount}, role={current_user.role}")
            tax_rate = db.tax_rates.find_one({
                'role': current_user.role,
                'min_income': {'$lte': amount},
                'max_income': {'$gte': amount}
            })
            if tax_rate:
                tax = round(amount * tax_rate['rate'], 2)
                explanation = tax_rate['description']
                logging.info(f"Tax calculated: tax={tax}, explanation={explanation}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': trans('tax_no_rate_found', default='No tax rate found')}), 400
        else:
            logging.error(f"Form validation failed: {form.errors}")
            flash(trans('tax_invalid_input', default='Invalid input. Please check your amount.'), 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': trans('tax_invalid_input', default='Invalid input')}), 400
    return render_template('common_features/taxation/taxation.html',
                         section='calculate',
                         form=form,
                         role=current_user.role,
                         tax_rates=tax_rates,
                         t=trans,
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/payment_info', methods=['GET'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def payment_info():
    db = get_mongo_db()
    locations = list(db.tax_locations.find())
    return render_template('common_features/taxation/taxation.html',
                         section='payment_info',
                         locations=locations,
                         t=trans,
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/reminders', methods=['GET', 'POST'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def reminders():
    form = ReminderForm()
    db = get_mongo_db()
    if request.method == 'POST' and form.validate_on_submit():
        reminder = {
            'user_id': current_user.id,
            'message': form.message.data,
            'reminder_date': form.reminder_date.data,
            'created_at': datetime.datetime.utcnow()
        }
        db.reminders.insert_one(reminder)
        flash(trans('tax_reminder_added', default='Reminder added successfully'), 'success')
        return redirect(url_for('taxation_bp.reminders'))
    reminders = list(db.reminders.find({'user_id': current_user.id}))
    return render_template('common_features/taxation/taxation.html',
                         section='reminders',
                         form=form,
                         reminders=reminders,
                         t=trans,
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/admin/rates', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_tax_rates():
    form = TaxRateForm()
    db = get_mongo_db()
    if request.method == 'POST' and form.validate_on_submit():
        tax_rate = {
            'role': form.role.data,
            'min_income': form.min_income.data,
            'max_income': form.max_income.data,
            'rate': form.rate.data,
            'description': form.description.data
        }
        db.tax_rates.insert_one(tax_rate)
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
    db = get_mongo_db()
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact = request.form.get('contact')
        if name and address and contact:
            db.tax_locations.insert_one({
                'name': name,
                'address': address,
                'contact': contact
            })
            flash(trans('tax_location_added', default='Location added successfully'), 'success')
            return redirect(url_for('taxation_bp.manage_payment_locations'))
        else:
            flash(trans('tax_invalid_input', default='Invalid input. Please check your fields.'), 'danger')
    locations = list(db.tax_locations.find())
    return render_template('common_features/taxation/taxation.html',
                         section='admin_locations',
                         locations=locations,
                         t=trans,
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/admin/deadlines', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_tax_deadlines():
    db = get_mongo_db()
    if request.method == 'POST':
        deadline_date = request.form.get('deadline_date')
        description = request.form.get('description')
        if deadline_date and description:
            try:
                deadline_date = datetime.datetime.strptime(deadline_date, '%Y-%m-%d')
                db.tax_deadlines.insert_one({
                    'deadline_date': deadline_date,
                    'description': description
                })
                flash(trans('tax_deadline_added', default='Deadline added successfully'), 'success')
            except ValueError:
                flash(trans('tax_invalid_date', default='Invalid date format'), 'danger')
        else:
            flash(trans('tax_invalid_input', default='Invalid input. Please check your fields.'), 'danger')
        return redirect(url_for('taxation_bp.manage_tax_deadlines'))
    deadlines = list(db.tax_deadlines.find())
    return render_template('common_features/taxation/taxation.html',
                         section='admin_deadlines',
                         deadlines=deadlines,
                         t=trans,
                         lang=session.get('lang', 'en'))
