from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from .models import NewsArticle, db
from ..utils import requires_role

common_bp = Blueprint('common_bp', __name__)

# User-facing routes
@common_bp.route('/news', methods=['GET'])
@requires_role(['personal', 'trader', 'agent', 'admin'])
@login_required
def news_list():
    articles = NewsArticle.query.filter_by(is_active=True).order_by(NewsArticle.published_at.desc()).all()
    return render_template('common_features/news_list.html', articles=articles)

@common_bp.route('/news/<int:article_id>', methods=['GET'])
@requires_role(['personal', 'trader', 'agent', 'admin'])
@login_required
def news_detail(article_id):
    article = NewsArticle.query.get_or_404(article_id)
    if not article.is_active:
        flash('Article not found', 'danger')
        return redirect(url_for('common_bp.news_list'))
    return render_template('common_features/news_detail.html', article=article)

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
            flash('Title and content are required', 'danger')
        else:
            article = NewsArticle(
                title=title,
                content=content,
                source_type='admin',
                source_link=source_link,
                category=category,
                is_verified=True,
                is_active=True
            )
            db.session.add(article)
            db.session.commit()
            flash('News article added successfully', 'success')
            return redirect(url_for('common_bp.news_management'))
    
    articles = NewsArticle.query.all()
    return render_template('common_features/news_admin.html', articles=articles)

@common_bp.route('/admin/news_management/edit/<int:article_id>', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def edit_news(article_id):
    article = NewsArticle.query.get_or_404(article_id)
    if request.method == 'POST':
        article.title = request.form.get('title')
        article.content = request.form.get('content')
        article.source_link = request.form.get('source_link')
        article.category = request.form.get('category')
        article.is_active = 'is_active' in request.form
        
        if not article.title or not article.content:
            flash('Title and content are required', 'danger')
        else:
            db.session.commit()
            flash('News article updated successfully', 'success')
            return redirect(url_for('common_bp.news_management'))
    
    return render_template('common_features/news_admin.html', article=article, edit_mode=True)

@common_bp.route('/admin/news_management/delete/<int:article_id>', methods=['POST'])
@requires_role('admin')
@login_required
def delete_news(article_id):
    article = NewsArticle.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    flash('News article deleted successfully', 'success')
    return redirect(url_for('common_bp.news_management'))

# Placeholder for background API fetch (to be implemented with APScheduler/Celery)
# def fetch_news_from_api_scheduled_job():
#     # Use NewsAPI or similar to fetch articles
#     # Filter by keywords: "finance", "Naira", "CBN", "tax"
#     # Check for duplicates by title/source_link
#     # Store with source_type='api', is_verified=False, is_active=False
#     pass