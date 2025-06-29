from flask import Blueprint

common_bp = Blueprint('common_bp', __name__, template_folder='templates', 'templates/taxation')

from . import routes
