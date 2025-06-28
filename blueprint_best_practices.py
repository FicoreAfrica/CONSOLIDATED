"""
Best practices for using translations in Flask blueprints.
"""

from flask import Blueprint, render_template, session, request, g
from translations import trans, get_translations, get_module_translations

# Method 1: Simple blueprint with basic translation support
simple_bp = Blueprint('simple', __name__)

@simple_bp.route('/simple')
def simple_route():
    return render_template('simple.html', 
                         trans=lambda key, **kwargs: trans(key, **kwargs))

# Method 2: Blueprint with language-specific optimizations
optimized_bp = Blueprint('optimized', __name__)

@optimized_bp.before_request
def before_request():
    """Set up translation context for each request."""
    g.current_lang = session.get('lang', 'en')
    g.trans = lambda key, **kwargs: trans(key, lang=g.current_lang, **kwargs)

@optimized_bp.route('/optimized')
def optimized_route():
    # Translation function is already available in g.trans
    return render_template('optimized.html')

# Method 3: Blueprint with module-specific translations (for performance)
module_specific_bp = Blueprint('bills', __name__)

@module_specific_bp.route('/bills')
def bills_dashboard():
    current_lang = session.get('lang', 'en')
    
    # Pre-load only the translations needed for this module
    bill_translations = get_module_translations('bill', current_lang)
    core_translations = get_module_translations('core', current_lang)
    main_translations = get_module_translations('main', current_lang)
    
    return render_template('bills/dashboard.html',
                         trans=lambda key, **kwargs: trans(key, lang=current_lang, **kwargs),
                         # Optional: pass specific translation dicts for performance
                         bill_trans=bill_translations,
                         core_trans=core_translations,
                         main_trans=main_translations)

# Method 4: Blueprint with context processor (recommended for complex blueprints)
comprehensive_bp = Blueprint('comprehensive', __name__)

@comprehensive_bp.app_context_processor
def inject_comprehensive_translations():
    """Inject translations and related utilities into all templates."""
    current_lang = session.get('lang', 'en')
    
    return {
        'trans': lambda key, **kwargs: trans(key, lang=current_lang, **kwargs),
        'current_lang': current_lang,
        'is_english': current_lang == 'en',
        'is_hausa': current_lang == 'ha',
        'rtl': current_lang in ['ar'],  # For future RTL language support
        'lang_direction': 'rtl' if current_lang in ['ar'] else 'ltr'
    }

@comprehensive_bp.route('/comprehensive')
def comprehensive_route():
    # All translation utilities are automatically available in templates
    return render_template('comprehensive.html')