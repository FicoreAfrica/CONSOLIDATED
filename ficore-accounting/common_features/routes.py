from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from translations import trans
from utils import requires_role, get_mongo_db
import bleach
import datetime
import logging

common_bp = Blueprint('common_bp', __name__)

# Sanitize HTML inputs to prevent XSS
def sanitize_input(text):
    allowed_tags = ['p', 'b', 'i', 'strong', 'em', 'ul', 'ol', 'li', 'a']
    allowed_attributes = {'a': ['href', 'target']}
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes)

@common_bp.route('/news', methods=['GET'])
@requires_role(['personal', 'trader', 'agent', 'admin'])
@login_required
def news_list():
    db = get_mongo_db()
    search_query = request.args.get('search', '')
    category = request.args.get('category', '')
    query = {'is_active': True}
    
    if search_query:
        query['$or'] = [
            {'title': {'$regex': search_query, '$options': 'i'}},
            {'content': {'$regex': search_query, '$options': 'i'}}
        ]
    if category:
        query['category'] = category
    
    articles = list(db.news.find(query).sort('published_at', -1))
    categories = db.news.distinct('category')
    logging.info(f"News list queried: search={search_query}, category={category}, articles={len(articles)}")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify([{
            'id': str(article['_id']),
            'title': article['title'],
            'category': article.get('category', ''),
            'published_at': article['published_at'].strftime('%Y-%m-%d'),
            'content': article['content'][:100] + '...' if len(article['content']) > 100 else article['content']
        } for article in articles])
    
    return render_template('common_features/news.html', 
                         section='list', 
                         articles=articles, 
                         categories=categories,
                         t=trans, 
                         lang=session.get('lang', 'en'))

@common_bp.route('/news/<article_id>', methods=['GET'])
@requires_role(['personal', 'trader', 'agent', 'admin'])
@login_required
def news_detail(article_id):
    db = get_mongo_db()
    try:
        article = db.news.find_one({'_id': ObjectId(article_id), 'is_active': True})
    except:
        article = None
    
    if not article:
        logging.warning(f"News article not found: id={article_id}")
        flash(trans('news_article_not_found', default='Article not found'), 'danger')
        return redirect(url_for('common_bp.news_list'))
    
    logging.info(f"News detail viewed: id={article_id}, title={article['title']}")
    return render_template('common_features/news.html', 
                         section='detail', 
                         article=article, 
                         t=trans, 
                         lang=session.get('lang', 'en'))

@common_bp.route('/admin/news_management', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def news_management():
    db = get_mongo_db()
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        source_link = request.form.get('source_link')
        category = request.form.get('category')
        is_active = 'is_active' in request.form
        
        if not title or not content:
            logging.error(f"News creation failed: title={title}, content={content}")
            flash(trans('news_title_content_required', default='Title and content are required'), 'danger')
        else:
            sanitized_content = sanitize_input(content)
            article = {
                'title': title,
                'content': sanitized_content,
                'source_link': source_link if source_link else None,
                'category': category if category else None,
                'is_active': is_active,
                'published_at': datetime.datetime.utcnow(),
                'created_by': current_user.id
            }
            db.news.insert_one(article)
            logging.info(f"News article created: title={title}")
            flash(trans('news_article_added', default='News article added successfully'), 'success')
            return redirect(url_for('common_bp.news_management'))
    
    articles = list(db.news.find().sort('published_at', -1))
    return render_template('common_features/news.html', 
                         section='admin', 
                         articles=articles, 
                         t=trans, 
                         lang=session.get('lang', 'en'))

@common_bp.route('/admin/news_management/edit/<article_id>', methods=['GET', 'POST'])
@requires_role('admin')
@login_required
def edit_news(article_id):
    db = get_mongo_db()
    try:
        article = db.news.find_one({'_id': ObjectId(article_id)})
    except:
        article = None
    
    if not article:
        logging.warning(f"Edit news article not found: id={article_id}")
        flash(trans('news_article_not_found', default='Article not found'), 'danger')
        return redirect(url_for('common_bp.news_management'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        source_link = request.form.get('source_link')
        category = request.form.get('category')
        is_active = 'is_active' in request.form
        
        if not title or not content:
            logging.error(f"News update failed: title={title}, content={content}")
            flash(trans('news_title_content_required', default='Title and content are required'), 'danger')
        else:
            sanitized_content = sanitize_input(content)
            db.news.update_one(
                {'_id': ObjectId(article_id)},
                {'$set': {
                    'title': title,
                    'content': sanitized_content,
                    'source_link': source_link if source_link else None,
                    'category': category if category else None,
                    'is_active': is_active,
                    'updated_at': datetime.datetime.utcnow()
                }}
            )
            logging.info(f"News article updated: id={article_id}, title={title}")
            flash(trans('news_article_updated', default='News article updated successfully'), 'success')
            return redirect(url_for('common_bp.news_management'))
    
    return render_template('common_features/news.html', 
                         section='edit', 
                         article=article, 
                         t=trans, 
                         lang=session.get('lang', 'en'))

@common_bp.route('/admin/news_management/delete/<article_id>', methods=['POST'])
@requires_role('admin')
@login_required
def delete_news(article_id):
    db = get_mongo_db()
    try:
        result = db.news.delete_one({'_id': ObjectId(article_id)})
        if result.deleted_count > 0:
            logging.info(f"News article deleted: id={article_id}")
            flash(trans('news_article_deleted', default='News article deleted successfully'), 'success')
        else:
            logging.warning(f"News article not found for deletion: id={article_id}")
            flash(trans('news_article_not_found', default='Article not found'), 'danger')
    except:
        logging.error(f"Error deleting news article: id={article_id}")
        flash(trans('news_error', default='Error deleting article'), 'danger')
    return redirect(url_for('common_bp.news_management'))

# Seed initial articles (run once, e.g., via a setup script)
def seed_news():
    db = get_mongo_db()
    if db.news.count_documents({}) == 0:
        articles = [
            {
                'title': 'Welcome to iHatch Cohort 4 – Next Steps Facore News',
                'content': """
                    <p>Congratulations to all innovators selected for the iHatch Startup Support Programme Cohort 4, a 5-month intensive incubation program by NITDA and JICA, running from October 2024 to March 2025. This program empowers early-stage Nigerian startups in sectors like fintech, agritech, and healthtech with mentorship, training, and resources to scale their ventures.</p>
                    <p><strong>Next Steps:</strong></p>
                    <p>Let's work together to empower Nigeria's innovation landscape, one startup at a time!</p>
                """,
                'source_link': 'https://programs.startup.gov.ng/ihatch',
                'category': 'Startups',
                'is_active': True,
                'published_at': datetime.datetime(2025, 6, 2),
                'created_by': 'admin'
            },
            {
                'title': 'Fintech Innovations Driving Financial Inclusion in Nigeria',
                'content': """
                    <p>Nigerian fintech startups are revolutionizing access to financial services. Companies like Paystack and Flutterwave are enabling seamless digital payments, while others like PiggyVest are promoting savings and investment among the youth.</p>
                    <p>These innovations align with Nigeria's Digital Economy Policy, fostering economic growth and job creation.</p>
                """,
                'source_link': None,
                'category': 'Fintech',
                'is_active': True,
                'published_at': datetime.datetime(2025, 6, 1),
                'created_by': 'admin'
            },
            {
                'title': 'Agritech Solutions Transforming Nigerian Agriculture',
                'content': """
                    <p>Agritech startups are addressing challenges in Nigeria's agricultural sector by providing farmers with access to markets, financing, and technology. Innovations like precision farming tools and mobile apps for market data are boosting productivity.</p>
                    <p>These solutions support sustainable development and food security across the nation.</p>
                """,
                'source_link': None,
                'category': 'Agritech',
                'is_active': True,
                'published_at': datetime.datetime(2025, 5, 30),
                'created_by': 'admin'
            }
        ]
        db.news.insert_many(articles)
        logging.info("Seeded initial news articles")
