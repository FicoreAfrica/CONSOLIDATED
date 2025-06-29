from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required
from translations import trans
from utils import requires_role

common_bp = Blueprint('common_bp', __name__)

# User-facing routes
@common_bp.route('/news', methods=['GET'])
@requires_role(['personal', 'trader', 'agent', 'admin'])
@login_required
def news_list():
    # Placeholder - would need to implement with MongoDB
    articles = []
    return render_template('common_features/news_list.html', articles=articles, t=trans, lang=session.get('lang', 'en'))

@common_bp.route('/news/<int:article_id>', methods=['GET'])
@requires_role(['personal', 'trader', 'agent', 'admin'])
@login_required
def news_detail(article_id):
    # Placeholder - would need to implement with MongoDB
    article = None
    if not article:
        flash(trans('news_article_not_found', default='Article not found'), 'danger')
        return redirect(url_for('common_bp.news_list'))
    return render_template('common_features/news_detail.html', article=article, t=trans, lang=session.get('lang', 'en'))

# Admin-facing routes
@common_bp.route('/admin/news_management', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def news_management():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        source_link = request.form.get('source_link')
        category = request.form.get('category')
        
        if not title or not content:
            flash(trans('news_title_content_required', default='Title and content are required'), 'danger')
        else:
            # Placeholder - would need to implement with MongoDB
            flash(trans('news_article_added', default='News article added successfully'), 'success')
            return redirect(url_for('common_bp.news_management'))
    
    articles = []  # Placeholder
    return render_template('common_features/news_admin.html', articles=articles, t=trans, lang=session.get('lang', 'en'))

@common_bp.route('/admin/news_management/edit/<int:article_id>', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def edit_news(article_id):
    # Placeholder - would need to implement with MongoDB
    article = None
    if request.method == 'POST':
        # Update logic would go here
        flash(trans('news_article_updated', default='News article updated successfully'), 'success')
        return redirect(url_for('common_bp.news_management'))
    
    return render_template('common_features/news_admin.html', article=article, edit_mode=True, t=trans, lang=session.get('lang', 'en'))

@common_bp.route('/admin/news_management/delete/<int:article_id>', methods=['POST'])
@requires_role('admin')
@login_required
def delete_news(article_id):
    # Placeholder - would need to implement with MongoDB
    flash(trans('news_article_deleted', default='News article deleted successfully'), 'success')
    return redirect(url_for('common_bp.news_management'))