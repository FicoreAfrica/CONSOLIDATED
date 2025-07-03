from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from translations import trans
from utils import (
    requires_role, get_mongo_db,
    PERSONAL_TOOLS, PERSONAL_NAV, PERSONAL_EXPLORE_FEATURES,
    BUSINESS_TOOLS, BUSINESS_NAV, BUSINESS_EXPLORE_FEATURES,
    AGENT_TOOLS, AGENT_NAV, AGENT_EXPLORE_FEATURES,
    ALL_TOOLS, ADMIN_NAV, ADMIN_EXPLORE_FEATURES
)
import logging
import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)

taxation_bp = Blueprint('taxation_bp', __name__, template_folder='templates/common_features/taxation')

# Forms
class TaxCalculationForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(message=trans('tax_amount_required', default='Amount is required')), NumberRange(min=0, message=trans('tax_amount_non_negative', default='Amount must be non-negative'))], render_kw={'class': 'form-control'})
    taxpayer_type = SelectField('Taxpayer Type', choices=[
        ('paye', trans('tax_paye', default='PAYE (Personal)')),
        ('small_business', trans('tax_small_business', default='Small Business')),
        ('cit', trans('tax_cit', default='CIT (Company Income Tax)'))
    ], validators=[DataRequired(message=trans('tax_type_required', default='Taxpayer type is required'))], render_kw={'class': 'form-select'})
    business_size = SelectField('Business Size', choices=[
        ('', trans('tax_select_size', default='Select Size')),
        ('small', trans('tax_small', default='Small (< ₦25M)')),
        ('medium', trans('tax_medium', default='Medium (₦26M-₦100M)')),
        ('large', trans('tax_large', default='Large (> ₦100M)'))
    ], validators=[DataRequired(message=trans('tax_business_size_required', default='Business size is required'))], render_kw={'class': 'form-select'})
    submit = SubmitField(trans('tax_calculate', default='Calculate Tax'), render_kw={'class': 'btn btn-primary w-100'})

class TaxRateForm(FlaskForm):
    role = SelectField('Role', choices=[
        ('personal', trans('tax_personal', default='Personal')),
        ('trader', trans('tax_trader', default='Trader')),
        ('agent', trans('tax_agent', default='Agent')),
        ('company', trans('tax_company', default='Company'))
    ], validators=[DataRequired(message=trans('tax_role_required', default='Role is required'))], render_kw={'class': 'form-select'})
    min_income = FloatField('Minimum Income', validators=[DataRequired(message=trans('tax_min_income_required', default='Minimum income is required')), NumberRange(min=0, message=trans('tax_min_income_non_negative', default='Minimum income must be non-negative'))], render_kw={'class': 'form-control'})
    max_income = FloatField('Maximum Income', validators=[DataRequired(message=trans('tax_max_income_required', default='Maximum income is required')), NumberRange(min=0, message=trans('tax_max_income_non_negative', default='Maximum income must be non-negative'))], render_kw={'class': 'form-control'})
    rate = FloatField('Rate', validators=[DataRequired(message=trans('tax_rate_required', default='Rate is required')), NumberRange(min=0, max=1, message=trans('tax_rate_range', default='Rate must be between 0 and 1'))], render_kw={'class': 'form-control'})
    description = StringField('Description', validators=[DataRequired(message=trans('tax_description_required', default='Description is required'))], render_kw={'class': 'form-control'})
    submit = SubmitField(trans('tax_add_rate', default='Add Tax Rate'), render_kw={'class': 'btn btn-primary w-100'})

class ReminderForm(FlaskForm):
    message = StringField('Message', validators=[DataRequired(message=trans('tax_message_required', default='Message is required'))], render_kw={'class': 'form-control'})
    reminder_date = DateField('Reminder Date', validators=[DataRequired(message=trans('tax_reminder_date_required', default='Reminder date is required'))], render_kw={'class': 'form-control'})
    submit = SubmitField(trans('tax_add_reminder', default='Add Reminder'), render_kw={'class': 'btn btn-primary w-100'})

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
            {'role': 'personal', 'min_income': 0.0, 'max_income': 800000.0, 'rate': 0.0, 'description': trans('tax_rate_personal_0', default='0% tax rate for personal income up to 800,000 NGN')},
            {'role': 'personal', 'min_income': 800001.0, 'max_income': 3000000.0, 'rate': 0.15, 'description': trans('tax_rate_personal_15', default='15% tax rate for personal income from 800,001 to 3,000,000 NGN')},
            {'role': 'personal', 'min_income': 3000001.0, 'max_income': 12000000.0, 'rate': 0.18, 'description': trans('tax_rate_personal_18', default='18% tax rate for personal income from 3,000,001 to 12,000,000 NGN')},
            {'role': 'personal', 'min_income': 12000001.0, 'max_income': float('inf'), 'rate': 0.25, 'description': trans('tax_rate_personal_25', default='25% tax rate for personal income above 12,000,000 NGN')},
            {'role': 'company', 'min_income': 0.0, 'max_income': 25000000.0, 'rate': 0.0, 'description': trans('tax_rate_company_small', default='0% for revenue up to ₦25M (Small Business)')},
            {'role': 'company', 'min_income': 25000001.0, 'max_income': 100000000.0, 'rate': 0.20, 'description': trans('tax_rate_company_medium', default='20% for revenue between ₦25M and ₦100M (Medium Business)')},
            {'role': 'company', 'min_income': 100000001.0, 'max_income': float('inf'), 'rate': 0.30, 'description': trans('tax_rate_company_large', default='30% for revenue above ₦100M (Large Business)')},
            {'role': 'company', 'min_income': 0.0, 'max_income': 25000000.0, 'rate': 0.0, 'description': trans('tax_rate_cit_small', default='0% CIT for turnover ≤ ₦25M')},
            {'role': 'company', 'min_income': 25000001.0, 'max_income': 100000000.0, 'rate': 0.20, 'description': trans('tax_rate_cit_medium', default='20% CIT for turnover ₦25M - ₦100M')},
            {'role': 'company', 'min_income': 100000001.0, 'max_income': float('inf'), 'rate': 0.30, 'description': trans('tax_rate_cit_large', default='30% CIT for turnover > ₦100M')}
        ]
        db.tax_rates.insert_many(tax_rates)
        logger.info("Seeded tax rates")

    # Seed payment locations
    if db.payment_locations.count_documents({}) == 0:
        locations = [
            {'name': 'Lagos NRS Office', 'address': '123 Broad Street, Lagos', 'contact': '+234-1-2345678'},
            {'name': 'Abuja NRS Office', 'address': '456 Garki Road, Abuja', 'contact': '+234-9-8765432'}
        ]
        db.payment_locations.insert_many(locations)
        logger.info("Seeded tax locations")

    # Seed tax reminders
    if db.tax_reminders.count_documents({}) == 0:
        reminders = [
            {'user_id': 'admin', 'message': trans('tax_reminder_quarterly', default='File quarterly tax return with NRS'), 'reminder_date': datetime.datetime(2025, 9, 30), 'created_at': datetime.datetime.utcnow()}
        ]
        db.tax_reminders.insert_many(reminders)
        logger.info("Seeded reminders")

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
            logger.info(f"POST /calculate: user={current_user.id}, amount={amount}, taxpayer_type={taxpayer_type}, business_size={business_size}")

            total_tax = 0.0
            explanation = ""

            if taxpayer_type == 'paye':
                total_tax = calculate_paye(amount)
                explanation = trans('tax_paye_explanation', default="Progressive PAYE: 0% up to ₦800,000, 15% up to ₦3,000,000, 18% up to ₦12,000,000, 25% above ₦12,000,000 + {:.0%} Development Levy").format(0.02 if amount <= 5000000 else 0.04)

            elif taxpayer_type == 'small_business':
                total_tax = calculate_cit(amount)
                if amount <= 25000000:
                    explanation = trans('tax_small_business_explanation_small', default="0% for revenue up to ₦25M")
                elif amount <= 100000000:
                    explanation = trans('tax_small_business_explanation_medium', default="20% for revenue between ₦25M and ₦100M")
                else:
                    explanation = trans('tax_small_business_explanation_large', default="30% for revenue above ₦100M")
                explanation += trans('tax_additional_taxes', default=" + 3% Tertiary Education Tax + {:.0%} Development Levy").format(0.02 if amount <= 5000000 else 0.04)

            elif taxpayer_type == 'cit':
                if business_size not in ['small', 'medium', 'large']:
                    flash(trans('tax_invalid_business_size', default='Invalid business size selected'), 'warning')
                    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
                    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
                    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
                    return render_template(
                        'common_features/taxation/taxation.html',
                        section='calculate',
                        form=form,
                        tax_rates=serialized_tax_rates,
                        t=trans,
                        lang=session.get('lang', 'en'),
                        tools=tools,
                        nav_items=nav_items,
                        bottom_nav_items=bottom_nav_items
                    )
                total_tax = calculate_cit(amount)
                if business_size == 'small':
                    explanation = trans('tax_cit_explanation_small', default="0% for companies with turnover ≤ ₦25M")
                elif business_size == 'medium':
                    explanation = trans('tax_cit_explanation_medium', default="20% for companies with turnover ₦25M - ₦100M")
                elif business_size == 'large':
                    explanation = trans('tax_cit_explanation_large', default="30% for companies with turnover > ₦100M")
                explanation += trans('tax_additional_taxes', default=" + 3% Tertiary Education Tax + {:.0%} Development Levy").format(0.02 if amount <= 5000000 else 0.04)

            logger.info(f"Tax calculated: user={current_user.id}, tax={total_tax}, explanation={explanation}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'tax': total_tax, 'explanation': explanation, 'amount': amount})
            tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
            nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
            bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
            return render_template(
                'common_features/taxation/taxation.html',
                section='result',
                tax=total_tax,
                explanation=explanation,
                amount=amount,
                form=form,
                tax_rates=serialized_tax_rates,
                t=trans,
                lang=session.get('lang', 'en'),
                tools=tools,
                nav_items=nav_items,
                bottom_nav_items=bottom_nav_items
            )
        else:
            logger.error(f"Form validation failed: user={current_user.id}, errors={form.errors}")
            flash(trans('tax_invalid_input', default='Invalid input. Please check your amount and selections.'), 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': trans('tax_invalid_input', default='Invalid input')}), 400

    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
    return render_template(
        'common_features/taxation/taxation.html',
        section='calculate',
        form=form,
        role=current_user.role,
        tax_rates=serialized_tax_rates,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=tools,
        nav_items=nav_items,
        bottom_nav_items=bottom_nav_items
    )

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
    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
    return render_template(
        'common_features/taxation/taxation.html',
        section='payment_info',
        locations=serialized_locations,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=tools,
        nav_items=nav_items,
        bottom_nav_items=bottom_nav_items
    )

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
        logger.info(f"Reminder added: user={current_user.id}, message={form.message.data}")
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
    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
    return render_template(
        'common_features/taxation/taxation.html',
        section='reminders',
        form=form,
        reminders=serialized_reminders,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=tools,
        nav_items=nav_items,
        bottom_nav_items=bottom_nav_items
    )

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
        logger.info(f"Tax rate added: user={current_user.id}, role={form.role.data}, rate={form.rate.data}")
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
    return render_template(
        'common_features/taxation/taxation.html',
        section='admin_rates',
        form=form,
        rates=serialized_rates,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=ALL_TOOLS,
        nav_items=ADMIN_EXPLORE_FEATURES,
        bottom_nav_items=ADMIN_NAV
    )

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
            logger.info(f"Payment location added: user={current_user.id}, name={name}")
            flash(trans('tax_location_added', default='Location added successfully'), 'success')
            return redirect(url_for('taxation_bp.manage_payment_locations'))
        else:
            logger.error(f"Invalid input for payment location: user={current_user.id}, name={name}, address={address}, contact={contact}")
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
    return render_template(
        'common_features/taxation/taxation.html',
        section='admin_locations',
        locations=serialized_locations,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=ALL_TOOLS,
        nav_items=ADMIN_EXPLORE_FEATURES,
        bottom_nav_items=ADMIN_NAV
    )

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
                logger.info(f"Tax deadline added: user={current_user.id}, description={description}")
                flash(trans('tax_deadline_added', default='Deadline added successfully'), 'success')
            except ValueError:
                logger.error(f"Invalid date format for deadline: user={current_user.id}, date={deadline_date}")
                flash(trans('tax_invalid_date', default='Invalid date format'), 'danger')
        else:
            logger.error(f"Invalid input for deadline: user={current_user.id}, date={deadline_date}, description={description}")
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
    return render_template(
        'common_features/taxation/taxation.html',
        section='admin_deadlines',
        deadlines=serialized_deadlines,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=ALL_TOOLS,
        nav_items=ADMIN_EXPLORE_FEATURES,
        bottom_nav_items=ADMIN_NAV
    )
