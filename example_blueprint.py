from flask import Blueprint, render_template, session, g
from translations import trans, get_translations

# Example blueprint
example_bp = Blueprint('example', __name__)

@example_bp.route('/example')
def example_route():
    """Example route showing how to pass translations to templates."""
    
    # Get the current language from session (defaults to 'en')
    current_lang = session.get('lang', 'en')
    
    # Method 1: Pass the trans function directly (recommended)
    # This allows templates to call trans() with any key
    template_data = {
        'trans': lambda key, **kwargs: trans(key, lang=current_lang, **kwargs),
        # ... other template variables
    }
    
    # Method 2: Alternative - use get_translations helper
    # This creates a translation function bound to the current language
    translations = get_translations(current_lang)
    template_data = {
        **translations,  # This adds 'trans' function to template context
        # ... other template variables
    }
    
    return render_template('example.html', **template_data)

# For context processors (global template variables)
@example_bp.app_context_processor
def inject_translations():
    """Make translations available to all templates in this blueprint."""
    current_lang = session.get('lang', 'en')
    return {
        'trans': lambda key, **kwargs: trans(key, lang=current_lang, **kwargs),
        'current_lang': current_lang
    }