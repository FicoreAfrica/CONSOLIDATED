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
    # Convert ObjectId to string for JSON serialization
    serialized_tax_rates = [
        {
            'role': rate['role'],
            'min_income': rate['min_income'],
            'max_income': rate['max_income'],
            'rate': rate['rate'],
            'description': rate['description'],
            '_id': str(rate['_id'])  # Convert ObjectId to string
        } for rate in tax_rates
    ]
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
                                     tax_rates=serialized_tax_rates,
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
                         tax_rates=serialized_tax_rates,
                         t=trans,
                         lang=session.get('lang', 'en'))

@taxation_bp.route('/payment_info', methods=['GET'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def payment_info():
    db = get_mongo_db()
    locations = list(db.tax_locations.find())
    # Convert ObjectId to string for safety
    serialized_locations = [
        {
            'name': loc['name'],
            'address': loc['address'],
            'contact': loc['contact'],
            '_id': str(loc['_id'])
        } for loc in locations
    ]
    return render_template('common_features/taxation/taxation.html',
                         section='payment_info',
                         locations=serialized_locations,
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
    # Convert ObjectId and dates for template
    serialized_reminders = [
        {
            'message': rem['message'],
            'reminder_date': rem['reminder_date'],
            'created_at': rem['created_at'],
            '_id': str(rem['_id']),
            'user_id': str(rem['user_id'])
        } for rem in reminders
    ]
    return render_template('common_features/taxation/taxation.html',
                         section='reminders',
                         form=form,
                         reminders=serialized_reminders,
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
    serialized_rates = [
        {
            'role': rate['role'],
            'min_income': rate['min_income'],
            'max_income': rate['max_income'],
            'rate': rate['rate'],
            'description': rate['description'],
            '_id': str(rate['_id'])
        } for rate in rates
    ]
    return render_template('common_features/taxation/taxation.html',
                         section='admin_rates',
                         form=form,
                         rates=serialized_rates,
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
    serialized_locations = [
        {
            'name': loc['name'],
            'address': loc['address'],
            'contact': loc['contact'],
            '_id': str(loc['_id'])
        } for loc in locations
    ]
    return render_template('common_features/taxation/taxation.html',
                         section='admin_locations',
                         locations=serialized_locations,
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
    serialized_deadlines = [
        {
            'deadline_date': dl['deadline_date'],
            'description': dl['description'],
            '_id': str(dl['_id'])
        } for dl in deadlines
    ]
    return render_template('common_features/taxation/taxation.html',
                         section='admin_deadlines',
                         deadlines=serialized_deadlines,
                         t=trans,
                         lang=session.get('lang', 'en'))

def seed_tax_data():
    db = get_mongo_db()
    if db.tax_rates.count_documents({}) == 0:
        tax_rates = [
            {
                'role': 'personal',
                'min_income': 0.0,
                'max_income': 300000.0,
                'rate': 0.07,
                'description': '7% tax rate for personal income up to 300,000 NGN'
            },
            {
                'role': 'personal',
                'min_income': 300001.0,
                'max_income': 600000.0,
                'rate': 0.11,
                'description': '11% tax rate for personal income between 300,001 and 600,000 NGN'
            },
            {
                'role': 'trader',
                'min_income': 0.0,
                'max_income': 500000.0,
                'rate': 0.05,
                'description': '5% tax rate for trader turnover up to 500,000 NGN'
            },
            {
                'role': 'trader',
                'min_income': 500001.0,
                'max_income': 1000000.0,
                'rate': 0.08,
                'description': '8% tax rate for trader turnover between 500,001 and 1,000,000 NGN'
            },
            {
                'role': 'agent',
                'min_income': 0.0,
                'max_income': 400000.0,
                'rate': 0.06,
                'description': '6% tax rate for agent income up to 400,000 NGN'
            }
        ]
        db.tax_rates.insert_many(tax_rates)
        logging.info("Seeded tax rates")

    if db.tax_locations.count_documents({}) == 0:
        locations = [
            {
                'name': 'Lagos Tax Office',
                'address': '123 Broad Street, Lagos',
                'contact': '+234-1-2345678'
            },
            {
                'name': 'Abuja Tax Office',
                'address': '456 Garki Road, Abuja',
                'contact': '+234-9-8765432'
            }
        ]
        db.tax_locations.insert_many(locations)
        logging.info("Seeded tax locations")

    if db.reminders.count_documents({}) == 0:
        reminders = [
            {
                'user_id': 'admin',  # Replace with actual user ID after models.py
                'message': 'File quarterly tax return',
                'reminder_date': datetime.datetime(2025, 9, 30),
                'created_at': datetime.datetime.utcnow()
            }
        ]
        db.reminders.insert_many(reminders)
        logging.info("Seeded reminders")
