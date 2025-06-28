from flask import session
from translations import trans, get_translations

def setup_global_translations(app):
    """Set up global translation context processor for the entire app."""
    
    @app.context_processor
    def inject_global_translations():
        """Make translations available to ALL templates globally."""
        current_lang = session.get('lang', 'en')
        return {
            'trans': lambda key, **kwargs: trans(key, lang=current_lang, **kwargs),
            'current_lang': current_lang,
            'available_languages': ['en', 'ha'],
            'language_names': {'en': 'English', 'ha': 'Hausa'}
        }