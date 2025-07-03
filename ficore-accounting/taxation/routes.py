from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, DateField, SelectField, SubmitField, BooleanField
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

taxation_bp = Blueprint('taxation_bp', __name__, template_folder='templates/taxation')

# Forms
class TaxCalculationForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(message=trans('tax_amount_required', default='Amount is required')), NumberRange(min=0, message=trans('tax_amount_non_negative', default='Amount must be non-negative'))], render_kw={'class': 'form-control'})
    taxpayer_type = SelectField('Taxpayer Type', choices=[
        ('paye', trans('tax_paye', default='PAYE (Personal)')),
        ('small_business', trans('tax_small_business', default='Small Business')),
        ('cit', trans('tax_cit', default='CIT (Company Income Tax)')),
        ('vat', trans('tax_vat', default='VAT (Value Added Tax)'))
    ], validators=[DataRequired(message=trans('tax_type_required', default='Taxpayer type is required'))], render_kw={'class': 'form-select'})
    business_size = SelectField('Business Size', choices=[
        ('', trans('tax_select_size', default='Select Size')),
        ('small', trans('tax_small', default='Small (≤ ₦50M)')),
        ('large', trans('tax_large', default='Large (> ₦50M)'))
    ], validators=[DataRequired(message=trans('tax_business_size_required', default='Business size is required'))], render_kw={'class': 'form-select'})
    vat_category = SelectField('VAT Category', choices=[
        ('', trans('tax_select_category', default='Select Category')),
        ('food', trans('tax_food', default='Food')),
        ('healthcare', trans('tax_healthcare', default='Healthcare')),
        ('education', trans('tax_education', default='Education')),
        ('rent', trans('tax_rent', default='Rent')),
        ('power', trans('tax_power', default='Power')),
        ('baby_products', trans('tax_baby_products', default='Baby Products')),
        ('other', trans('tax_other', default='Other'))
    ], render_kw={'class': 'form-select'})
    is_business_vat = BooleanField('Business VAT Credit', render_kw={'class': 'form-check-input'})
    submit = SubmitField(trans('tax_calculate', default='Calculate Tax'), render_kw={'class': 'btn btn-primary w-100'})

class TaxRateForm(FlaskForm):
    role = SelectField('Role', choices=[
        ('personal', trans('tax_personal', default='Personal')),
        ('trader', trans('tax_trader', default='Trader')),
        ('agent', trans('tax_agent', default='Agent')),
        ('company', trans('tax_company', default='Company')),
        ('vat', trans('tax_vat', default='VAT'))
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
def calculate_paye_tax(amount):
    taxable_income = amount
    if amount <= 1000000:
        taxable_income = max(0, amount - 200000)  # Apply rent relief
    tax = 0
    if taxable_income <= 800000:
        tax = 0
    elif taxable_income <= 3000000:
        tax += (taxable_income - 800000) * 0.15
    elif taxable_income <= 12000000:
        tax += 2200000 * 0.15
        tax += (taxable_income - 3000000) * 0.18
    elif taxable_income <= 25000000:
        tax += 2200000 * 0.15
        tax += 9000000 * 0.18
        tax += (taxable_income - 12000000) * 0.21
    elif taxable_income <= 50000000:
        tax += 2200000 * 0.15
        tax += 9000000 * 0.18
        tax += 13000000 * 0.21
        tax += (taxable_income - 25000000) * 0.23
    else:
        tax += 2200000 * 0.15
        tax += 9000000 * 0.18
        tax += 13000000 * 0.21
        tax += 25000000 * 0.23
        tax += (taxable_income - 50000000) * 0.25
    return round(tax, 2), trans('tax_paye_explanation', default="Progressive PAYE: 0% up to ₦800,000, 15% up to ₦3M, 18% up to ₦12M, 21% up to ₦25M, 23% up to ₦50M, 25% above ₦50M" + (" + ₦200,000 rent relief" if amount <= 1000000 else ""))

def calculate_vat(amount, category, is_business=False):
    exempt_categories = ["food", "healthcare", "education", "rent", "power", "baby_products"]
    if category in exempt_categories:
        return 0.0, trans('tax_vat_exempt', default=f"{category.capitalize()} is VAT-exempt")
    vat_rate = 0.075
    vat_due = amount * vat_rate
    explanation = trans('tax_vat_applied', default=f"{vat_rate*100}% VAT applied")
    if is_business:
        vat_due = 0.0
        explanation = trans('tax_vat_reclaimed', default="Input VAT reclaimed for business")
    return round(vat_due, 2), explanation

def calculate_cit(turnover):
    current_year = datetime.datetime.now().year
    if turnover <= 50000000:
        tax = 0.0
        explanation = trans('tax_cit_explanation_small', default="0% CIT for turnover ≤ ₦50M, simplified return, no audit")
        simplified_return = True
        audit_required = False
    else:
        rate = 0.275 if current_year == 2025 else 0.25
        tax = turnover * rate
        explanation = trans('tax_cit_explanation_large', default=f"{rate*100}% CIT for turnover > ₦50M")
        simplified_return = False
        audit_required = True
    return round(tax, 2), explanation, simplified_return, audit_required

def tax_summary(name, gross_income, turnover, vat_amount, vat_category, is_business_vat):
    paye, paye_explanation = calculate_paye_tax(gross_income)
    cit, cit_explanation, simplified_return, audit_required = calculate_cit(turnover)
    vat, vat_explanation = calculate_vat(vat_amount, vat_category, is_business_vat)
    return {
        "name": name,
        "gross_income": gross_income,
        "monthly_paye": round(paye / 12, 2),
        "annual_paye": paye,
        "paye_explanation": paye_explanation,
        "sme_turnover": turnover,
        "sme_cit": cit,
        "cit_explanation": cit_explanation,
        "simplified_return": simplified_return,
        "audit_required": audit_required,
        "vat_amount": vat_amount,
        "vat_tax": vat,
        "vat_explanation": vat_explanation
    }

# Database Seeding
def seed_tax_data():
    db = get_mongo_db()
    for collection in ['tax_rates', 'vat_rules', 'payment_locations', 'tax_reminders']:
        if collection not in db.list_collection_names():
            db.create_collection(collection)

    if db.tax_rates.count_documents({}) == 0:
        tax_rates = [
            {'role': 'personal', 'min_income': 0.0, 'max_income': 800000.0, 'rate': 0.0, 'description': trans('tax_rate_personal_0', default='0% tax rate for personal income up to ₦800,000 (with ₦200,000 rent relief if income ≤ ₦1M)')},
            {'role': 'personal', 'min_income': 800001.0, 'max_income': 3000000.0, 'rate': 0.15, 'description': trans('tax_rate_personal_15', default='15% tax rate for personal income from ₦800,001 to ₦3,000,000')},
            {'role': 'personal', 'min_income': 3000001.0, 'max_income': 12000000.0, 'rate': 0.18, 'description': trans('tax_rate_personal_18', default='18% tax rate for personal income from ₦3,000,001 to ₦12,000,000')},
            {'role': 'personal', 'min_income': 12000001.0, 'max_income': 25000000.0, 'rate': 0.21, 'description': trans('tax_rate_personal_21', default='21% tax rate for personal income from ₦12,000,001 to ₦25,000,000')},
            {'role': 'personal', 'min_income': 25000001.0, 'max_income': 50000000.0, 'rate': 0.23, 'description': trans('tax_rate_personal_23', default='23% tax rate for personal income from ₦25,000,001 to ₦50,000,000')},
            {'role': 'personal', 'min_income': 50000001.0, 'max_income': float('inf'), 'rate': 0.25, 'description': trans('tax_rate_personal_25', default='25% tax rate for personal income above ₦50,000,000')},
            {'role': 'company', 'min_income': 0.0, 'max_income': 50000000.0, 'rate': 0.0, 'description': trans('tax_rate_cit_small', default='0% CIT for turnover ≤ ₦50M, simplified return, no audit')},
            {'role': 'company', 'min_income': 50000001.0, 'max_income': float('inf'), 'rate': 0.25, 'description': trans('tax_rate_cit_large_2026', default='25% CIT for turnover > ₦50M (2026 onward)')}
        ]
        db.tax_rates.insert_many(tax_rates)
        logger.info("Seeded tax rates")

    if db.vat_rules.count_documents({}) == 0:
        vat_rules = [
            {'category': cat, 'vat_exempt': True, 'description': trans(f'tax_vat_exempt_{cat}', default=f'{cat.capitalize()} is exempt from VAT')} for cat in ['food', 'healthcare', 'education', 'rent', 'power', 'baby_products']
        ] + [
            {'category': 'business_credit', 'vat_exempt': False, 'description': trans('tax_vat_reclaimed', default='Input VAT reclaimed for business')}
        ]
        db.vat_rules.insert_many(vat_rules)
        logger.info("Seeded VAT rules")

    if db.payment_locations.count_documents({}) == 0:
        locations = [
            {'name': 'Lagos NRS Office', 'address': '123 Broad Street, Lagos', 'contact': '+234-1-2345678'},
            {'name': 'Abuja NRS Office', 'address': '456 Garki Road, Abuja', 'contact': '+234-9-8765432'}
        ]
        db.payment_locations.insert_many(locations)
        logger.info("Seeded tax locations")

    if db.tax_reminders.count_documents({}) == 0:
        reminders = [
            {'user_id': 'admin', 'message': trans('tax_reminder_quarterly', default='File quarterly tax return with NRS'), 'reminder_date': datetime.datetime(2026, 3, 31), 'created_at': datetime.datetime.utcnow()}
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
    vat_rules = list(db.vat_rules.find())
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
    serialized_vat_rules = [
        {
            'category': rule['category'],
            'vat_exempt': rule['vat_exempt'],
            'description': rule['description'],
            '_id': str(rule['_id'])
        } for rule in vat_rules
    ]

    if request.method == 'POST':
        if form.validate_on_submit():
            amount = form.amount.data
            taxpayer_type = form.taxpayer_type.data
            business_size = form.business_size.data if taxpayer_type in ['small_business', 'cit'] else None
            vat_category = form.vat_category.data if taxpayer_type == 'vat' else None
            is_business_vat = form.is_business_vat.data if taxpayer_type == 'vat' else False
            logger.info(f"POST /calculate: user={current_user.id}, amount={amount}, taxpayer_type={taxpayer_type}, business_size={business_size}, vat_category={vat_category}, is_business_vat={is_business_vat}")

            total_tax = 0.0
            explanation = ""
            simplified_return = False
            audit_required = False

            if taxpayer_type == 'paye':
                total_tax, explanation = calculate_paye_tax(amount)
            elif taxpayer_type == 'small_business' or taxpayer_type == 'cit':
                if business_size not in ['small', 'large']:
                    flash(trans('tax_invalid_business_size', default='Invalid business size selected'), 'warning')
                    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
                    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
                    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
                    return render_template(
                        'taxation/taxation.html',
                        section='calculate',
                        form=form,
                        tax_rates=serialized_tax_rates,
                        vat_rules=serialized_vat_rules,
                        t=trans,
                        lang=session.get('lang', 'en'),
                        tools=tools,
                        nav_items=nav_items,
                        bottom_nav_items=bottom_nav_items,
                        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
                    )
                total_tax, explanation, simplified_return, audit_required = calculate_cit(amount)
            elif taxpayer_type == 'vat':
                if not vat_category:
                    flash(trans('tax_invalid_vat_category', default='VAT category required'), 'warning')
                    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
                    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
                    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
                    return render_template(
                        'taxation/taxation.html',
                        section='calculate',
                        form=form,
                        tax_rates=serialized_tax_rates,
                        vat_rules=serialized_vat_rules,
                        t=trans,
                        lang=session.get('lang', 'en'),
                        tools=tools,
                        nav_items=nav_items,
                        bottom_nav_items=bottom_nav_items,
                        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
                    )
                total_tax, explanation = calculate_vat(amount, vat_category, is_business_vat)

            logger.info(f"Tax calculated: user={current_user.id}, tax={total_tax}, explanation={explanation}, simplified_return={simplified_return}, audit_required={audit_required}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'tax': total_tax,
                    'explanation': explanation,
                    'amount': amount,
                    'simplified_return': simplified_return,
                    'audit_required': audit_required
                })
            tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
            nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
            bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if “

System: It looks like your response was cut off. Based on the pattern in the provided code, I can complete the `calculate_tax` route and include the remaining routes to ensure the full code is returned with the fixes applied. Below is the complete Flask code, including the corrected `seed_tax_data` function and all routes, with no syntax errors.

### Complete Fixed Code

```python
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, DateField, SelectField, SubmitField, BooleanField
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

taxation_bp = Blueprint('taxation_bp', __name__, template_folder='templates/taxation')

# Forms
class TaxCalculationForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(message=trans('tax_amount_required', default='Amount is required')), NumberRange(min=0, message=trans('tax_amount_non_negative', default='Amount must be non-negative'))], render_kw={'class': 'form-control'})
    taxpayer_type = SelectField('Taxpayer Type', choices=[
        ('paye', trans('tax_paye', default='PAYE (Personal)')),
        ('small_business', trans('tax_small_business', default='Small Business')),
        ('cit', trans('tax_cit', default='CIT (Company Income Tax)')),
        ('vat', trans('tax_vat', default='VAT (Value Added Tax)'))
    ], validators=[DataRequired(message=trans('tax_type_required', default='Taxpayer type is required'))], render_kw={'class': 'form-select'})
    business_size = SelectField('Business Size', choices=[
        ('', trans('tax_select_size', default='Select Size')),
        ('small', trans('tax_small', default='Small (≤ ₦50M)')),
        ('large', trans('tax_large', default='Large (> ₦50M)'))
    ], validators=[DataRequired(message=trans('tax_business_size_required', default='Business size is required'))], render_kw={'class': 'form-select'})
    vat_category = SelectField('VAT Category', choices=[
        ('', trans('tax_select_category', default='Select Category')),
        ('food', trans('tax_food', default='Food')),
        ('healthcare', trans('tax_healthcare', default='Healthcare')),
        ('education', trans('tax_education', default='Education')),
        ('rent', trans('tax_rent', default='Rent')),
        ('power', trans('tax_power', default='Power')),
        ('baby_products', trans('tax_baby_products', default='Baby Products')),
        ('other', trans('tax_other', default='Other'))
    ], render_kw={'class': 'form-select'})
    is_business_vat = BooleanField('Business VAT Credit', render_kw={'class': 'form-check-input'})
    submit = SubmitField(trans('tax_calculate', default='Calculate Tax'), render_kw={'class': 'btn btn-primary w-100'})

class TaxRateForm(FlaskForm):
    role = SelectField('Role', choices=[
        ('personal', trans('tax_personal', default='Personal')),
        ('trader', trans('tax_trader', default='Trader')),
        ('agent', trans('tax_agent', default='Agent')),
        ('company', trans('tax_company', default='Company')),
        ('vat', trans('tax_vat', default='VAT'))
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
def calculate_paye_tax(amount):
    taxable_income = amount
    if amount <= 1000000:
        taxable_income = max(0, amount - 200000)  # Apply rent relief
    tax = 0
    if taxable_income <= 800000:
        tax = 0
    elif taxable_income <= 3000000:
        tax += (taxable_income - 800000) * 0.15
    elif taxable_income <= 12000000:
        tax += 2200000 * 0.15
        tax += (taxable_income - 3000000) * 0.18
    elif taxable_income <= 25000000:
        tax += 2200000 * 0.15
        tax += 9000000 * 0.18
        tax += (taxable_income - 12000000) * 0.21
    elif taxable_income <= 50000000:
        tax += 2200000 * 0.15
        tax += 9000000 * 0.18
        tax += 13000000 * 0.21
        tax += (taxable_income - 25000000) * 0.23
    else:
        tax += 2200000 * 0.15
        tax += 9000000 * 0.18
        tax += 13000000 * 0.21
        tax += 25000000 * 0.23
        tax += (taxable_income - 50000000) * 0.25
    return round(tax, 2), trans('tax_paye_explanation', default="Progressive PAYE: 0% up to ₦800,000, 15% up to ₦3M, 18% up to ₦12M, 21% up to ₦25M, 23% up to ₦50M, 25% above ₦50M" + (" + ₦200,000 rent relief" if amount <= 1000000 else ""))

def calculate_vat(amount, category, is_business=False):
    exempt_categories = ["food", "healthcare", "education", "rent", "power", "baby_products"]
    if category in exempt_categories:
        return 0.0, trans('tax_vat_exempt', default=f"{category.capitalize()} is VAT-exempt")
    vat_rate = 0.075
    vat_due = amount * vat_rate
    explanation = trans('tax_vat_applied', default=f"{vat_rate*100}% VAT applied")
    if is_business:
        vat_due = 0.0
        explanation = trans('tax_vat_reclaimed', default="Input VAT reclaimed for business")
    return round(vat_due, 2), explanation

def calculate_cit(turnover):
    current_year = datetime.datetime.now().year
    if turnover <= 50000000:
        tax = 0.0
        explanation = trans('tax_cit_explanation_small', default="0% CIT for turnover ≤ ₦50M, simplified return, no audit")
        simplified_return = True
        audit_required = False
    else:
        rate = 0.275 if current_year == 2025 else 0.25
        tax = turnover * rate
        explanation = trans('tax_cit_explanation_large', default=f"{rate*100}% CIT for turnover > ₦50M")
        simplified_return = False
        audit_required = True
    return round(tax, 2), explanation, simplified_return, audit_required

def tax_summary(name, gross_income, turnover, vat_amount, vat_category, is_business_vat):
    paye, paye_explanation = calculate_paye_tax(gross_income)
    cit, cit_explanation, simplified_return, audit_required = calculate_cit(turnover)
    vat, vat_explanation = calculate_vat(vat_amount, vat_category, is_business_vat)
    return {
        "name": name,
        "gross_income": gross_income,
        "monthly_paye": round(paye / 12, 2),
        "annual_paye": paye,
        "paye_explanation": paye_explanation,
        "sme_turnover": turnover,
        "sme_cit": cit,
        "cit_explanation": cit_explanation,
        "simplified_return": simplified_return,
        "audit_required": audit_required,
        "vat_amount": vat_amount,
        "vat_tax": vat,
        "vat_explanation": vat_explanation
    }

# Database Seeding
def seed_tax_data():
    db = get_mongo_db()
    for collection in ['tax_rates', 'vat_rules', 'payment_locations', 'tax_reminders']:
        if collection not in db.list_collection_names():
            db.create_collection(collection)

    if db.tax_rates.count_documents({}) == 0:
        tax_rates = [
            {'role': 'personal', 'min_income': 0.0, 'max_income': 800000.0, 'rate': 0.0, 'description': trans('tax_rate_personal_0', default='0% tax rate for personal income up to ₦800,000 (with ₦200,000 rent relief if income ≤ ₦1M)')},
            {'role': 'personal', 'min_income': 800001.0, 'max_income': 3000000.0, 'rate': 0.15, 'description': trans('tax_rate_personal_15', default='15% tax rate for personal income from ₦800,001 to ₦3,000,000')},
            {'role': 'personal', 'min_income': 3000001.0, 'max_income': 12000000.0, 'rate': 0.18, 'description': trans('tax_rate_personal_18', default='18% tax rate for personal income from ₦3,000,001 to ₦12,000,000')},
            {'role': 'personal', 'min_income': 12000001.0, 'max_income': 25000000.0, 'rate': 0.21, 'description': trans('tax_rate_personal_21', default='21% tax rate for personal income from ₦12,000,001 to ₦25,000,000')},
            {'role': 'personal', 'min_income': 25000001.0, 'max_income': 50000000.0, 'rate': 0.23, 'description': trans('tax_rate_personal_23', default='23% tax rate for personal income from ₦25,000,001 to ₦50,000,000')},
            {'role': 'personal', 'min_income': 50000001.0, 'max_income': float('inf'), 'rate': 0.25, 'description': trans('tax_rate_personal_25', default='25% tax rate for personal income above ₦50,000,000')},
            {'role': 'company', 'min_income': 0.0, 'max_income': 50000000.0, 'rate': 0.0, 'description': trans('tax_rate_cit_small', default='0% CIT for turnover ≤ ₦50M, simplified return, no audit')},
            {'role': 'company', 'min_income': 50000001.0, 'max_income': float('inf'), 'rate': 0.25, 'description': trans('tax_rate_cit_large_2026', default='25% CIT for turnover > ₦50M (2026 onward)')}
        ]
        db.tax_rates.insert_many(tax_rates)
        logger.info("Seeded tax rates")

    if db.vat_rules.count_documents({}) == 0:
        vat_rules = [
            {'category': cat, 'vat_exempt': True, 'description': trans(f'tax_vat_exempt_{cat}', default=f'{cat.capitalize()} is exempt from VAT')} for cat in ['food', 'healthcare', 'education', 'rent', 'power', 'baby_products']
        ] + [
            {'category': 'business_credit', 'vat_exempt': False, 'description': trans('tax_vat_reclaimed', default='Input VAT reclaimed for business')}
        ]
        db.vat_rules.insert_many(vat_rules)
        logger.info("Seeded VAT rules")

    if db.payment_locations.count_documents({}) == 0:
        locations = [
            {'name': 'Lagos NRS Office', 'address': '123 Broad Street, Lagos', 'contact': '+234-1-2345678'},
            {'name': 'Abuja NRS Office', 'address': '456 Garki Road, Abuja', 'contact': '+234-9-8765432'}
        ]
        db.payment_locations.insert_many(locations)
        logger.info("Seeded tax locations")

    if db.tax_reminders.count_documents({}) == 0:
        reminders = [
            {'user_id': 'admin', 'message': trans('tax_reminder_quarterly', default='File quarterly tax return with NRS'), 'reminder_date': datetime.datetime(2026, 3, 31), 'created_at': datetime.datetime.utcnow()}
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
    vat_rules = list(db.vat_rules.find())
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
    serialized_vat_rules = [
        {
            'category': rule['category'],
            'vat_exempt': rule['vat_exempt'],
            'description': rule['description'],
            '_id': str(rule['_id'])
        } for rule in vat_rules
    ]

    if request.method == 'POST':
        if form.validate_on_submit():
            amount = form.amount.data
            taxpayer_type = form.taxpayer_type.data
            business_size = form.business_size.data if taxpayer_type in ['small_business', 'cit'] else None
            vat_category = form.vat_category.data if taxpayer_type == 'vat' else None
            is_business_vat = form.is_business_vat.data if taxpayer_type == 'vat' else False
            logger.info(f"POST /calculate: user={current_user.id}, amount={amount}, taxpayer_type={taxpayer_type}, business_size={business_size}, vat_category={vat_category}, is_business_vat={is_business_vat}")

            total_tax = 0.0
            explanation = ""
            simplified_return = False
            audit_required = False

            if taxpayer_type == 'paye':
                total_tax, explanation = calculate_paye_tax(amount)
            elif taxpayer_type == 'small_business' or taxpayer_type == 'cit':
                if business_size not in ['small', 'large']:
                    flash(trans('tax_invalid_business_size', default='Invalid business size selected'), 'warning')
                    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
                    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
                    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
                    return render_template(
                        'taxation/taxation.html',
                        section='calculate',
                        form=form,
                        tax_rates=serialized_tax_rates,
                        vat_rules=serialized_vat_rules,
                        t=trans,
                        lang=session.get('lang', 'en'),
                        tools=tools,
                        nav_items=nav_items,
                        bottom_nav_items=bottom_nav_items,
                        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
                    )
                total_tax, explanation, simplified_return, audit_required = calculate_cit(amount)
            elif taxpayer_type == 'vat':
                if not vat_category:
                    flash(trans('tax_invalid_vat_category', default='VAT category required'), 'warning')
                    tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
                    nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
                    bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
                    return render_template(
                        'taxation/taxation.html',
                        section='calculate',
                        form=form,
                        tax_rates=serialized_tax_rates,
                        vat_rules=serialized_vat_rules,
                        t=trans,
                        lang=session.get('lang', 'en'),
                        tools=tools,
                        nav_items=nav_items,
                        bottom_nav_items=bottom_nav_items,
                        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
                    )
                total_tax, explanation = calculate_vat(amount, vat_category, is_business_vat)

            logger.info(f"Tax calculated: user={current_user.id}, tax={total_tax}, explanation={explanation}, simplified_return={simplified_return}, audit_required={audit_required}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'tax': total_tax,
                    'explanation': explanation,
                    'amount': amount,
                    'simplified_return': simplified_return,
                    'audit_required': audit_required
                })
            tools = PERSONAL_TOOLS if current_user.role == 'personal' else BUSINESS_TOOLS if current_user.role == 'trader' else AGENT_TOOLS if current_user.role == 'agent' else ALL_TOOLS
            nav_items = PERSONAL_EXPLORE_FEATURES if current_user.role == 'personal' else BUSINESS_EXPLORE_FEATURES if current_user.role == 'trader' else AGENT_EXPLORE_FEATURES if current_user.role == 'agent' else ADMIN_EXPLORE_FEATURES
            bottom_nav_items = PERSONAL_NAV if current_user.role == 'personal' else BUSINESS_NAV if current_user.role == 'trader' else AGENT_NAV if current_user.role == 'agent' else ADMIN_NAV
            return render_template(
                'taxation/taxation.html',
                section='result',
                tax=total_tax,
                explanation=explanation,
                amount=amount,
                simplified_return=simplified_return,
                audit_required=audit_required,
                form=form,
                tax_rates=serialized_tax_rates,
                vat_rules=serialized_vat_rules,
                t=trans,
                lang=session.get('lang', 'en'),
                tools=tools,
                nav_items=nav_items,
                bottom_nav_items=bottom_nav_items,
                policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
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
        'taxation/taxation.html',
        section='calculate',
        form=form,
        role=current_user.role,
        tax_rates=serialized_tax_rates,
        vat_rules=serialized_vat_rules,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=tools,
        nav_items=nav_items,
        bottom_nav_items=bottom_nav_items,
        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
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
        'taxation/taxation.html',
        section='payment_info',
        locations=serialized_locations,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=tools,
        nav_items=nav_items,
        bottom_nav_items=bottom_nav_items,
        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
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
        'taxation/taxation.html',
        section='reminders',
        form=form,
        reminders=serialized_reminders,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=tools,
        nav_items=nav_items,
        bottom_nav_items=bottom_nav_items,
        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
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
    vat_rules = list(db.vat_rules.find())
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
    serialized_vat_rules = [
        {
            'category': rule['category'],
            'vat_exempt': rule['vat_exempt'],
            'description': rule['description'],
            '_id': str(rule['_id'])
        } for rule in vat_rules
    ]
    return render_template(
        'taxation/taxation.html',
        section='admin_rates',
        form=form,
        rates=serialized_rates,
        vat_rules=serialized_vat_rules,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=ALL_TOOLS,
        nav_items=ADMIN_EXPLORE_FEATURES,
        bottom_nav_items=ADMIN_NAV,
        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
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
        'taxation/taxation.html',
        section='admin_locations',
        locations=serialized_locations,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=ALL_TOOLS,
        nav_items=ADMIN_EXPLORE_FEATURES,
        bottom_nav_items=ADMIN_NAV,
        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
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
        'taxation/taxation.html',
        section='admin_deadlines',
        deadlines=serialized_deadlines,
        t=trans,
        lang=session.get('lang', 'en'),
        tools=ALL_TOOLS,
        nav_items=ADMIN_EXPLORE_FEATURES,
        bottom_nav_items=ADMIN_NAV,
        policy_notice=trans('tax_policy_notice', default='New tax laws effective 1 January 2026: Rent relief of ₦200,000 for income ≤ ₦1M, VAT exemptions for essentials, 0% CIT for small businesses ≤ ₦50M with simplified returns, 25% CIT for large businesses, VAT credits for businesses.')
    )
