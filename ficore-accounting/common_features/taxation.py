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

# Forms
class TaxCalculationForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0)])
    taxpayer_type = SelectField('Taxpayer Type', choices=[
        ('paye', 'PAYE (Personal)'),
        ('small_business', 'Small Business'),
        ('cit', 'CIT (Company Income Tax)')
    ], validators=[DataRequired()])
    business_size = SelectField('Business Size', choices=[
        ('', 'Select Size'),
        ('small', 'Small (< ₦25M)'),
        ('medium', 'Medium (₦26M-₦100M)'),
        ('large', 'Large (> ₦100M)')
    ], validators=[DataRequired()])
    submit = SubmitField('Calculate Tax')

class TaxRateForm(FlaskForm):
    role = SelectField('Role', choices=[
        ('personal', 'Personal'),
        ('trader', 'Trader'),
        ('agent', 'Agent'),
        ('company', 'Company')
    ], validators=[DataRequired()])
    min_income = FloatField('Minimum Income', validators=[DataRequired(), NumberRange(min=0)])
    max_income = FloatField('Maximum Income', validators=[DataRequired(), NumberRange(min=0)])
    rate = FloatField('Rate', validators=[DataRequired(), NumberRange(min=0, max=1)])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Add Tax Rate')

class ReminderForm(FlaskForm):
    message = StringField('Message', validators=[DataRequired()])
    reminder_date = DateField('Reminder Date', validators=[DataRequired()])
    submit = SubmitField('Add Reminder')

# Tax Calculation Functions
def calculate_paye(gross_income):
    tax_brackets = [
        (800000.0, 0.0),  # 0% up to ₦800,000
        (3000000.0, 0.15),  # 15% from ₦800,001 to ₦3,000,000
        (12000000.0, 0.18),  # 18% from ₦3,000,001 to ₦12,000,000
        (float('inf'), 0.25)  # 25% above ₦12,000,000
    ]
    tax_due = 0.0
    taxable_income = gross_income
    last_limit = 0.0

    for limit, rate in tax_brackets:
        if taxable_income <= last_limit:
            break
        band_amount = min(taxable_income, limit) - last_limit
        if band_amount > 0:
            tax_due += band_amount * rate
        if taxable_income <= limit:
            break
        last_limit = limit

    # Add Development Levy
    levy_rate = 0.02 if gross_income <= 5000000 else 0.04
    tax_due += gross_income * levy_rate
    return round(tax_due, 2)

def calculate_cit(turnover):
    if turnover <= 25000000:
        tax = 0.0
    elif turnover <= 100000000:
        tax = turnover * 0.20
    else:
        tax = turnover * 0.30
    # Add Tertiary Education Tax for CIT (3% for non-zero turnover)
    tertiary_edu_tax = turnover * 0.03 if turnover > 0 else 0.0
    # Add Development Levy
    levy_rate = 0.02 if turnover <= 5000000 else 0.04
    tax += tertiary_edu_tax + (turnover * levy_rate)
    return round(tax, 2)

def tax_summary(name, gross_income, turnover):
    paye = calculate_paye(gross_income)
    cit = calculate_cit(turnover)
    return {
        "name": name,
        "gross_income": gross_income,
        "monthly_paye": round(paye / 12, 2),
        "annual_paye": paye,
        "sme_turnover": turnover,
        "sme_cit": cit
    }

# Database Seeding
def seed_tax_data():
    db = get_mongo_db()
    # Create collections if they don't exist
    for collection in ['tax_rates', 'payment_locations', 'tax_reminders']:
        if collection not in db.list_collection_names():
            db.create_collection(collection)

    # Seed tax rates
    if db.tax_rates.count_documents({}) == 0:
        tax_rates = [
            {'role': 'personal', 'min_income': 0.0, 'max_income': 800000.0, 'rate': 0.0, 'description': '0% tax rate for personal income up to 800,000 NGN'},
            {'role': 'personal', 'min_income': 800001.0, 'max_income': 3000000.0, 'rate': 0.15, 'description': '15% tax rate for personal income from 800,001 to 3,000,000 NGN'},
            {'role': 'personal', 'min_income': 3000001.0, 'max_income': 12000000.0, 'rate': 0.18, 'description': '18% tax rate for personal income from 3,000,001 to 12,000,000 NGN'},
            {'role': 'personal', 'min_income': 12000001.0, 'max_income': float('inf'), 'rate': 0.25, 'description': '25% tax rate for personal income above 12,000,000 NGN'},
            {'role': 'company', 'min_income': 0.0, 'max_income': 25000000.0, 'rate': 0.0, 'description': '0% for revenue up to ₦25M (Small Business)'},
            {'role': 'company', 'min_income': 25000001.0, 'max_income': 100000000.0, 'rate': 0.20, 'description': '20% for revenue between ₦25M and ₦100M (Medium Business)'},
            {'role': 'company', 'min_income': 100000001.0, 'max_income': float('inf'), 'rate': 0.30, 'description': '30% for revenue above ₦100M (Large Business)'},
            {'role': 'company', 'min_income': 0.0, 'max_income': 25000000.0, 'rate': 0.0, 'description': '0% CIT for turnover ≤ ₦25M'},
            {'role': 'company', 'min_income': 25000001.0, 'max_income': 100000000.0, 'rate': 0.20, 'description': '20% CIT for turnover ₦25M - ₦100M'},
            {'role': 'company', 'min_income': 100000001.0, 'max_income': float('inf'), 'rate': 0.30, 'description': '30% CIT for turnover > ₦100M'},
        ]
        db.tax_rates.insert_many(tax_rates)
        logging.info("Seeded tax rates")

    # Seed payment locations
    if db.payment_locations.count_documents({}) == 0:
        locations = [
            {'name': 'Lagos NRS Office', 'address': '123 Broad Street, Lagos', 'contact': '+234-1-2345678'},
            {'name': 'Abuja NRS Office', 'address': '456 Garki Road, Abuja', 'contact': '+234-9-8765432'}
        ]
        db.payment_locations.insert_many(locations)
        logging.info("Seeded tax locations")

    # Seed tax reminders
    if db.tax_reminders.count_documents({}) == 0:
        reminders = [
            {'user_id': 'admin', 'message': 'File quarterly tax return with NRS', 'reminder_date': datetime.datetime(2025, 9, 30), 'created_at': datetime.datetime.utcnow()}
        ]
        db.tax_reminders.insert_many(reminders)
        logging.info("Seeded reminders")

# Routes
@taxation_bp.route('/calculate', methods=['GET', 'POST'])
@requires_role(['personal', 'trader', 'agent', 'company'])
@login_required
def calculate_tax():
    form = TaxCalculationForm()
    db = get_mongo_db()
    tax_rates = list(db.tax_rates.find())
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
            taxpayer_type = form.taxpayer_type.data
            business_size = form.business_size.data if taxpayer_type in ['small_business', 'cit'] else None
            logging.info(f"POST /calculate: user={current_user.username}, amount={amount}, taxpayer_type={taxpayer_type}, business_size={business_size}")

            total_tax = 0.0
            explanation = ""

            if taxpayer_type == 'paye':
                total_tax = calculate_paye(amount)
                explanation = "Progressive PAYE: 0% up to ₦800,000, 15% up to ₦3,000,000, 18% up to ₦12,000,000, 25% above ₦12,000,000 + {:.0%} Development Levy".format(0.02 if amount <= 5000000 else 0.04)

            elif taxpayer_type == 'small_business':
                total_tax = calculate_cit(amount)
                if amount <= 25000000:
                    explanation = "0% for revenue up to ₦25M"
                elif amount <= 100000000:
                    explanation = "20% for revenue between ₦25M and ₦100M"
                else:
                    explanation = "30% for revenue above ₦100M"
                explanation += f" + 3% Tertiary Education Tax + {0.02*100 if amount <= 5000000 else 0.04*100}% Development Levy"

            elif taxpayer_type == 'cit':
                if business_size not in ['small', 'medium', 'large']:
                    flash(trans('tax_invalid_business_size', default='Invalid business size selected'), 'warning')
                    return render_template('common_features/taxation/taxation.html',
                                         section='calculate',
                                         form=form,
                                         tax_rates=serialized_tax_rates,
                                         t=trans,
                                         lang=session.get('lang', 'en'))
                total_tax = calculate_cit(amount)
                if business_size == 'small':
                    explanation = "0% for companies with turnover ≤ ₦25M"
                elif business_size == 'medium':
                    explanation = "20% for companies with turnover ₦25M - ₦100M"
                elif business_size == 'large':
                    explanation = "30% for companies with turnover > ₦100M"
                explanation += f" + 3% Tertiary Education Tax + {0.02*100 if amount <= 5000000 else 0.04*100}% Development Levy"

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
            logging.error(f"Form validation failed: {form.errors}")
            flash(trans('tax_invalid_input', default='Invalid input. Please check your amount and selections.'), 'danger')
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
@requires_role(['personal', 'trader', 'agent', 'company'])
@login_required
def payment_info():
    db = get_mongo_db()
    locations = list(db.payment_locations.find())
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
@requires_role(['personal', 'trader', 'agent', 'company'])
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
        db.tax_reminders.insert_one(reminder)
        flash(trans('tax_reminder_added', default='Reminder added successfully'), 'success')
        return redirect(url_for('taxation_bp.reminders'))
    reminders = list(db.tax_reminders.find({'user_id': current_user.id}))
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
            db.payment_locations.insert_one({
                'name': name,
                'address': address,
                'contact': contact
            })
            flash(trans('tax_location_added', default='Location added successfully'), 'success')
            return redirect(url_for('taxation_bp.manage_payment_locations'))
        else:
            flash(trans('tax_invalid_input', default='Invalid input. Please check your fields.'), 'danger')
    locations = list(db.payment_locations.find())
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
                db.tax_reminders.insert_one({
                    'deadline_date': deadline_date,
                    'description': description
                })
                flash(trans('tax_deadline_added', default='Deadline added successfully'), 'success')
            except ValueError:
                flash(trans('tax_invalid_date', default='Invalid date format'), 'danger')
        else:
            flash(trans('tax_invalid_input', default='Invalid input. Please check your fields.'), 'danger')
        return redirect(url_for('taxation_bp.manage_tax_deadlines'))
    deadlines = list(db.tax_reminders.find())
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
