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

general_bp = Blueprint('general_bp', __name__, template_folder='templates/general')

@general_bp.route('/home')
def home():
    lang = session.get('lang', 'en')
    return render_template('general/home.html', t=trans, lang=lang, is_public=not current_user.is_authenticated, title=trans('general_business_home', lang=lang))
