from flask import Blueprint, render_template
from translations import trans
from flask import session

general_bp = Blueprint('general_bp', __name__, template_folder='templates/general')

@general_bp.route('/home')
def home():
    lang = session.get('lang', 'en')
    return render_template('general/home.html', t=trans, lang=lang, is_public=not current_user.is_authenticated, title=trans('general_business_home', lang=lang))