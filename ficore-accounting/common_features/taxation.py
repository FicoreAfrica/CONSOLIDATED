from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField
from wtforms.validators import DataRequired
from translations import trans
from utils import requires_role, get_mongo_db

taxation_bp = Blueprint('taxation_bp', __name__, template_folder='templates')

class TaxCalculationForm(FlaskForm):
    amount = FloatField(trans('tax_amount', default='Amount'), validators=[DataRequired()])
    submit = SubmitField(trans('tax_calculate', default='Calculate Tax'))

@taxation_bp.route('/calculate', methods=['GET', 'POST'])
@requires_role(['personal', 'trader', 'agent'])
@login_required
def calculate_tax():
    form = TaxCalculationForm()
    if form.validate_on_submit():
        amount = form.amount.data
        role = current_user.role
        db = get_mongo_db()
        tax_rate = db.tax_rates.find_one({'role': role, 'min_income': {'$lte': amount}, 'max_income': {'$gte': amount}})
        if tax_rate:
            tax = amount * tax_rate['rate']
            explanation = tax_rate['description']
            return render_template('common_features/taxation/calculation_result.html', tax=tax, explanation=explanation, amount=amount, t=trans, lang=session.get('lang', 'en'))
        else:
            flash(trans('tax_no_rate_found', default='No tax rate found for your role and amount'), 'warning')
    return render_template('common_features/taxation/calculate.html', form=form, role=current_user.role, t=trans, lang=session.get('lang', 'en'))

@taxation_bp.route('/payment-info')
@requires_role(['personal', 'trader', 'agent'])
@login_required
def payment_info():
    db = get_mongo_db()
    locations = list(db.payment_locations.find())
    return render_template('common_features/taxation/payment_info.html', locations=locations, t=trans, lang=session.get('lang', 'en'))

@taxation_bp.route('/reminders')
@requires_role(['personal', 'trader', 'agent'])
@login_required
def reminders():
    db = get_mongo_db()
    reminders = list(db.tax_reminders.find({'user_id': current_user.id}))
    return render_template('common_features/taxation/reminders.html', reminders=reminders, t=trans, lang=session.get('lang', 'en'))

# Placeholder for admin routes
@taxation_bp.route('/admin/rates', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_tax_rates():
    # TODO: Implement tax rate management
    return trans('tax_manage_rates_admin', default='Manage Tax Rates (Admin)')

@taxation_bp.route('/admin/locations', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_payment_locations():
    # TODO: Implement payment location management
    return trans('tax_manage_locations_admin', default='Manage Payment Locations (Admin)')

@taxation_bp.route('/admin/deadlines', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def manage_tax_deadlines():
    # TODO: Implement tax deadline management
    return trans('tax_manage_deadlines_admin', default='Manage Tax Deadlines (Admin)')