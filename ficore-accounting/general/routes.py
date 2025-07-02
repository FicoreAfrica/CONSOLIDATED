from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from utils import BUSINESS_TOOLS, BUSINESS_NAV, ALL_TOOLS, ADMIN_NAV, trans_function
from translations import trans

general_bp = Blueprint('general_bp', __name__, url_prefix='/general')

@general_bp.route('/home')
@login_required
def home():
    """Trader homepage."""
    if current_user.role not in ['trader', 'admin']:
        flash(trans('general_access_denied', default='You do not have permission to access this page.'), 'danger')
        return redirect(url_for('app.index'))
    tools = BUSINESS_TOOLS if current_user.role == 'trader' else ALL_TOOLS
    nav_items = BUSINESS_NAV if current_user.role == 'trader' else ADMIN_NAV
    return render_template('general/home.html', tools=tools, nav_items=nav_items, t=trans, lang=session.get('lang', 'en'))

@general_bp.route('/about')
def about():
    """Public about page."""
    lang = session.get('lang', 'en')
    return render_template('general/about.html', t=trans, lang=lang)

@general_bp.route('/contact')
def contact():
    """Public contact page."""
    lang = session.get('lang', 'en')
    return render_template('general/contact.html', t=trans, lang=lang)
