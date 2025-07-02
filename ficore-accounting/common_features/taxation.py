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
    business_size = SelectField('Business Size', choices=[('', 'Select Size'), ('small', 'Small (< ₦25M)'), ('medium', 'Medium (₦26M-₦100M)'), ('large', 'Large (> ₦100M)')], validators=[DataRequired()])
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
    serialized_tax_rates = [
        {
            'role': rate['role'],
            'min_income': rate['min_income'],
            'max_income': rate['max_income'],
            'rate': rate['rate'],
            'description': rate['description'],
            '_id': str(rate['_id'])
        } for rate in tax_rates
    ]
    if request.method == 'POST':
        if form.validate_on_submit():
            amount = form.amount.data
            business_size = form.business_size.data if current_user.role in ['trader', 'agent'] else None
            logging.info(f"POST /calculate: user={current_user.username}, amount={amount}, role={current_user.role}, business_size={business_size}")
            tax_rate_query = {
                'role': current_user.role,
                'min_income': {'$lte': amount},
                'max_income': {'$gte': amount}
            }
            if business_size:
                tax_rate_query['description'] = {'$regex': business_size}
            tax_rate = db.tax_rates.find_one(tax_rate_query)
            if tax_rate:
                tax = round(amount * tax_rate['rate'], 2)
                levy_rate = 0.02 if amount <= 5000000 else 0.04
                levy = round(amount * levy_rate, 2)
                total_tax = tax + levy
                explanation = f"{tax_rate['description']} + {levy_rate*100}% Development Levy"
                logging.info(f"Tax calculated: tax={total_tax}, explanation={explanation}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'tax': total_tax, 'explanation': explanation, 'amount': amount})
                return render_template('common_features/taxation/taxation.html',
                                     section='result',
                                     tax=total_tax,
                                     explanation=explanation,
                                     amount=amount,
                                     form=form,
                                     tax_rates=serialized_tax_rates,
                                     t=trans,
                                     lang=session.get('lang', 'en'))
            else:
                logging.warning(f"No tax rate found for role={current_user.role}, amount={amount}, business_size={business_size}")
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

@taxation_bp.route('/understand_taxes', methods=['GET'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def understand_taxes():
    return render_template('common_features/taxation/taxation.html',
                         section='understand_taxes',
                         t=trans,
                         lang=session.get('lang', 'en'))

def seed_tax_data():
    db = get_mongo_db()
    if db.tax_rates.count_documents({}) == 0:
        tax_rates = [
            {
                'role': 'personal',
                'min_income': 0.0,
                'max_income': 800000.0,
                'rate': 0.0,
                'description': '0% tax rate for personal income up to 800,000 NGN (exempt)'
            },
            {
                'role': 'personal',
                'min_income': 800001.0,
                'max_income': 50000000.0,
                'rate': 0.07,
                'description': '7% tax rate for personal income between 800,001 and 50,000,000 NGN'
            },
            {
                'role': 'personal',
                'min_income': 50000001.0,
                'max_income': float('inf'),
                'rate': 0.25,
                'description': '25% tax rate for personal income above 50,000,000 NGN'
            },
            {
                'role': 'trader',
                'min_income': 0.0,
                'max_income': 25000000.0,
                'rate': 0.0,
                'description': '0% tax rate for small business turnover up to 25,000,000 NGN (small)'
            },
            {
                'role': 'trader',
                'min_income': 25000001.0,
                'max_income': 100000000.0,
                'rate': 0.25,
                'description': '25% tax rate for medium business turnover between 25,000,001 and 100,000,000 NGN (medium)'
            },
            {
                'role': 'trader',
                'min_income': 100000001.0,
                'max_income': float('inf'),
                'rate': 0.30,
                'description': '30% tax rate for large business turnover above 100,000,000 NGN (large)'
            },
            {
                'role': 'agent',
                'min_income': 0.0,
                'max_income': 25000000.0,
                'rate': 0.0,
                'description': '0% tax rate for small agent income up to 25,000,000 NGN (small)'
            },
            {
                'role': 'agent',
                'min_income': 25000001.0,
                'max_income': 100000000.0,
                'rate': 0.25,
                'description': '25% tax rate for medium agent income between 25,000,001 and 100,000,000 NGN (medium)'
            },
            {
                'role': 'agent',
                'min_income': 100000001.0,
                'max_income': float('inf'),
                'rate': 0.30,
                'description': '30% tax rate for large agent income above 100,000,000 NGN (large)'
            }
        ]
        db.tax_rates.insert_many(tax_rates)
        logging.info("Seeded tax rates")

    if db.tax_locations.count_documents({}) == 0:
        locations = [
            {
                'name': 'Lagos NRS Office',
                'address': '123 Broad Street, Lagos',
                'contact': '+234-1-2345678'
            },
            {
                'name': 'Abuja NRS Office',
                'address': '456 Garki Road, Abuja',
                'contact': '+234-9-8765432'
            }
        ]
        db.tax_locations.insert_many(locations)
        logging.info("Seeded tax locations")

    if db.reminders.count_documents({}) == 0:
        reminders = [
            {
                'user_id': 'admin',
                'message': 'File quarterly tax return with NRS',
                'reminder_date': datetime.datetime(2025, 9, 30),
                'created_at': datetime.datetime.utcnow()
            }
        ]
        db.reminders.insert_many(reminders)
        logging.info("Seeded reminders")
