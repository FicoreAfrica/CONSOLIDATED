from translations import trans
from flask_login import current_user
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from translations import trans
from utils import trans_function, requires_role, check_coin_balance, format_currency, format_date, get_mongo_db, is_admin, get_user_query
from bson import ObjectId
from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, SubmitField
from wtforms.validators import DataRequired, Optional
import logging

@general_bp.route('/home')
@login_required
def home():
    if current_user.role not in ['trader', 'admin']:
        return redirect(url_for('app.index'))
    tools = BUSINESS_TOOLS if current_user.role == 'trader' else ALL_TOOLS
    nav_items = BUSINESS_NAV if current_user.role == 'trader' else ADMIN_NAV
    return render_template('general/home.html', tools=tools, nav_items=nav_items, t=trans, lang=session.get('lang', 'en'))
