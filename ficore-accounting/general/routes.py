from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from utils import (
    PERSONAL_TOOLS, PERSONAL_NAV, PERSONAL_EXPLORE_FEATURES,
    BUSINESS_TOOLS, BUSINESS_NAV, BUSINESS_EXPLORE_FEATURES,
    AGENT_TOOLS, AGENT_NAV, AGENT_EXPLORE_FEATURES,
    ALL_TOOLS, ADMIN_NAV, ADMIN_EXPLORE_FEATURES,
    trans_function
)
from translations import trans

general_bp = Blueprint('general_bp', __name__, url_prefix='/general')

@general_bp.route('/home')
@login_required
def home():
    """Trader homepage."""
    if current_user.role not in ['trader', 'admin']:
        flash(trans('general_access_denied', default='You do not have permission to access this page.'), 'danger')
        return redirect(url_for('app.index'))
    
    # Role-based navigation data
    if current_user.role == 'trader':
        tools_for_template = BUSINESS_TOOLS
        explore_features_for_template = BUSINESS_EXPLORE_FEATURES
        bottom_nav_for_template = BUSINESS_NAV
    elif current_user.role == 'admin':
        tools_for_template = ALL_TOOLS
        explore_features_for_template = ADMIN_EXPLORE_FEATURES
        bottom_nav_for_template = ADMIN_NAV
    else:
        tools_for_template = []
        explore_features_for_template = []
        bottom_nav_for_template = []

    return render_template(
        'general/home.html',
        tools=tools_for_template,
        nav_items=explore_features_for_template,
        bottom_nav_items=bottom_nav_for_template,
        t=trans,
        lang=session.get('lang', 'en')
    )

@general_bp.route('/about')
def about():
    """Public about page."""
    # Role-based navigation data (optional, for consistency if navigation is displayed)
    if current_user.is_authenticated:
        if current_user.role == 'personal':
            tools_for_template = PERSONAL_TOOLS
            explore_features_for_template = PERSONAL_EXPLORE_FEATURES
            bottom_nav_for_template = PERSONAL_NAV
        elif current_user.role == 'trader':
            tools_for_template = BUSINESS_TOOLS
            explore_features_for_template = BUSINESS_EXPLORE_FEATURES
            bottom_nav_for_template = BUSINESS_NAV
        elif current_user.role == 'agent':
            tools_for_template = AGENT_TOOLS
            explore_features_for_template = AGENT_EXPLORE_FEATURES
            bottom_nav_for_template = AGENT_NAV
        elif current_user.role == 'admin':
            tools_for_template = ALL_TOOLS
            explore_features_for_template = ADMIN_EXPLORE_FEATURES
            bottom_nav_for_template = ADMIN_NAV
        else:
            tools_for_template = []
            explore_features_for_template = []
            bottom_nav_for_template = []
    else:
        tools_for_template = []
        explore_features_for_template = []
        bottom_nav_for_template = []

    return render_template(
        'general/about.html',
        tools=tools_for_template,
        nav_items=explore_features_for_template,
        bottom_nav_items=bottom_nav_for_template,
        t=trans,
        lang=session.get('lang', 'en')
    )

@general_bp.route('/contact')
def contact():
    """Public contact page."""
    # Role-based navigation data (optional, for consistency if navigation is displayed)
    if current_user.is_authenticated:
        if current_user.role == 'personal':
            tools_for_template = PERSONAL_TOOLS
            explore_features_for_template = PERSONAL_EXPLORE_FEATURES
            bottom_nav_for_template = PERSONAL_NAV
        elif current_user.role == 'trader':
            tools_for_template = BUSINESS_TOOLS
            explore_features_for_template = BUSINESS_EXPLORE_FEATURES
            bottom_nav_for_template = BUSINESS_NAV
        elif current_user.role == 'agent':
            tools_for_template = AGENT_TOOLS
            explore_features_for_template = AGENT_EXPLORE_FEATURES
            bottom_nav_for_template = AGENT_NAV
        elif current_user.role == 'admin':
            tools_for_template = ALL_TOOLS
            explore_features_for_template = ADMIN_EXPLORE_FEATURES
            bottom_nav_for_template = ADMIN_NAV
        else:
            tools_for_template = []
            explore_features_for_template = []
            bottom_nav_for_template = []
    else:
        tools_for_template = []
        explore_features_for_template = []
        bottom_nav_for_template = []

    return render_template(
        'general/contact.html',
        tools=tools_for_template,
        nav_items=explore_features_for_template,
        bottom_nav_items=bottom_nav_for_template,
        t=trans,
        lang=session.get('lang', 'en')
    )
