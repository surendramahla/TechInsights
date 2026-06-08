from flask import (Flask, render_template, url_for, flash, redirect,
                   request, abort, jsonify, send_from_directory, Response)
from extensions import db, bcrypt, login_manager, csrf, migrate, cache, sess, cors, swagger
from forms import (RegistrationForm, LoginForm, BlogForm,
                   CommentForm, UpdateProfileForm)
from models import User, Blog, Comment, Like, Category, Bookmark, CommentLike, Tag
from flask_login import login_user, current_user, logout_user, login_required
from services.cloudinary_service import init_cloudinary, upload_image, delete_image
from utils.image_utils import validate_image
import os
import secrets
import re
import bleach
from PIL import Image
from datetime import datetime
from config import get_config
from utils.helpers import log_activity
from models import ActivityLog

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

# ──────────────────────────────────────────────
# App Configuration
# ──────────────────────────────────────────────
app = Flask(__name__)

# Enforce secure proxies support so url_for(_external=True) uses https and correct host
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

config_class = get_config()
app.config.from_object(config_class)

# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from extensions import db, bcrypt, login_manager, csrf, mail, jwt, limiter, oauth, socketio, migrate, cache, sess, cors, swagger
db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
csrf.init_app(app)
mail.init_app(app)
jwt.init_app(app)
limiter.init_app(app)
oauth.init_app(app)

# Initialize production scalability and caching extensions
cache.init_app(app)
if app.config.get('SESSION_TYPE') and app.config.get('SESSION_TYPE') != 'null':
    sess.init_app(app)
migrate.init_app(app, db)

# Initialize CORS for REST APIs
cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

# Initialize Flasgger interactive Swagger documentation
from api.swagger import SWAGGER_CONFIG, SWAGGER_TEMPLATE
swagger.config = SWAGGER_CONFIG
swagger.template = SWAGGER_TEMPLATE
swagger.init_app(app)

# socketio scaling message queue using Redis in production
redis_url = app.config.get('REDIS_URL')
if app.config.get('FLASK_ENV') == 'production' and redis_url:
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet', message_queue=redis_url)
else:
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')

oauth.register(
    name='google',
    client_id=app.config.get('GOOGLE_CLIENT_ID'),
    client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

from auth import auth_bp
from api import api_bp
from admin import admin_bp
from media_route import media_bp
from realtime_routes import realtime_bp
from api.v1 import api_v1_bp

app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(media_bp)
app.register_blueprint(realtime_bp)
app.register_blueprint(api_v1_bp)

# Exempt stateless REST API blueprints from CSRF protection
csrf.exempt(api_bp)
csrf.exempt(api_v1_bp)

import sockets.events

# Initialize Cloudinary
init_cloudinary(app)

# ──────────────────────────────────────────────
# Allowed HTML tags for Quill content (bleach sanitisation)
# ──────────────────────────────────────────────
ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'strong', 'em', 'u', 's',
    'ol', 'ul', 'li',
    'a', 'img',
    'blockquote', 'code', 'pre',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'div', 'span',
]
ALLOWED_ATTRS = {
    '*':   ['class', 'style'],
    'a':   ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height'],
}

def sanitize_html(html_content):
    """Strip dangerous tags/attributes while preserving rich formatting."""
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True
    )

# ──────────────────────────────────────────────
# Profile picture helper
# ──────────────────────────────────────────────
def save_profile_picture(form_picture):
    """Save profile picture to Cloudinary; return secure url and public id."""
    result = upload_image(form_picture, folder="techinsights/profiles")
    if result:
        return result['url'], result['public_id']
    return None, None

# ──────────────────────────────────────────────
# Tag helper
# ──────────────────────────────────────────────
def process_tags(tag_string):
    """Convert comma-separated tag string to list of Tag objects."""
    if not tag_string:
        return []
    names = [t.strip().lower() for t in tag_string.split(',') if t.strip()]
    tags = []
    for name in names:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tags.append(tag)
    return tags

# ──────────────────────────────────────────────
# Database initialisation
# ──────────────────────────────────────────────
with app.app_context():
    # Only run db.create_all() if in development mode with SQLite,
    # otherwise let Alembic migrations create the tables in production.
    if app.config.get('DEBUG') and 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
        db.create_all()

    # ── Self-healing Database Migrations (Column & Index check) ──
    try:
        from sqlalchemy import inspect
        import sqlalchemy
        inspector = inspect(db.engine)
        
        # Check and add Category slug column
        if 'category' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('category')]
            if 'slug' not in columns:
                print("[Self-Heal] Category.slug missing. Migrating schema...")
                db.session.execute(sqlalchemy.text("ALTER TABLE category ADD COLUMN slug VARCHAR(100);"))
                db.session.execute(sqlalchemy.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_category_slug ON category(slug);"))
                db.session.commit()
                # Reload inspector
                inspector = inspect(db.engine)

        # Check and add Blog slug column and performance indexes
        if 'blog' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('blog')]
            if 'slug' not in columns:
                print("[Self-Heal] Blog.slug missing. Migrating schema...")
                db.session.execute(sqlalchemy.text("ALTER TABLE blog ADD COLUMN slug VARCHAR(255);"))
                db.session.execute(sqlalchemy.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_blog_slug ON blog(slug);"))
                db.session.commit()
            
            # Performance indexes
            try:
                db.session.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_blog_date ON blog(date_posted);"))
                db.session.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_blog_views ON blog(views);"))
                db.session.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_blog_blocked ON blog(is_blocked);"))
                db.session.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_blog_featured ON blog(is_featured);"))
                db.session.commit()
            except Exception as index_err:
                db.session.rollback()
                print(f"[Self-Heal] Blog indexing warning: {index_err}")

        # Check and add Comment date_posted index
        if 'comment' in inspector.get_table_names():
            try:
                db.session.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_comment_date ON comment(date_posted);"))
                db.session.commit()
            except Exception as comment_err:
                db.session.rollback()
                print(f"[Self-Heal] Comment indexing warning: {comment_err}")

        # ── Self-healing Missing Slugs Seeding ──
        from utils.seo import slugify
        
        # Populate Category slugs
        for cat in Category.query.filter((Category.slug == None) | (Category.slug == '')).all():
            cat.slug = slugify(cat.name)
            print(f"[Self-Heal] Generated slug '{cat.slug}' for category '{cat.name}'")
        
        # Populate Blog slugs
        for blog in Blog.query.filter((Blog.slug == None) | (Blog.slug == '')).all():
            blog.slug = slugify(blog.title)
            print(f"[Self-Heal] Generated slug '{blog.slug}' for blog '{blog.title[:20]}'")
            
        db.session.commit()

    except Exception as heal_err:
        print(f"[Self-Heal] Migration warning: {heal_err}")
        db.session.rollback()

    try:
        # Default admin user
        if not User.query.filter_by(is_admin=True).first():
            hashed_pw = bcrypt.generate_password_hash('admin').decode('utf-8')
            admin_user = User(username='admin', email='admin@example.com',
                              password=hashed_pw, is_admin=True)
            db.session.add(admin_user)
            db.session.commit()

        # Default categories
        default_categories = ['Technology', 'Lifestyle', 'Education', 'Entertainment', 'Others']
        if Category.query.count() == 0:
            for cat_name in default_categories:
                db.session.add(Category(name=cat_name))
            db.session.commit()
    except Exception as e:
        # Gracefully handle database seeding if tables do not exist yet (e.g. during migrations setup)
        print(f"[Startup] Seeding skipped (tables may not exist yet): {e}")
        db.session.rollback()


# ════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════

# ── Home / Feed ─────────────────────────────────
@app.route('/')
@app.route('/home')
def home():
    page         = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    category_id  = request.args.get('cat', type=int)
    tag_name     = request.args.get('tag', '').strip()

    if category_id:
        category = Category.query.get(category_id)
        if category:
            from utils.seo import slugify
            return redirect(url_for('category_detail', category_id=category.id, slug=category.slug or slugify(category.name)), code=301)

    query = Blog.query.options(
        db.joinedload(Blog.author),
        db.joinedload(Blog.category)
    ).filter_by(is_blocked=False)

    if search_query:
        query = query.filter(
            Blog.title.contains(search_query) | Blog.content.contains(search_query)
        )
    if tag_name:
        query = query.join(Blog.tags).filter(Tag.name == tag_name.lower())

    blogs      = query.order_by(Blog.date_posted.desc()).paginate(page=page, per_page=9)
    categories = Category.query.all()

    # Trending: top 5 by views
    trending = Blog.query.options(
        db.joinedload(Blog.author),
        db.joinedload(Blog.category)
    ).filter_by(is_blocked=False).order_by(Blog.views.desc()).limit(5).all()

    return render_template('index.html', blogs=blogs, categories=categories,
                           trending=trending, search_query=search_query,
                           active_cat=category_id, active_tag=tag_name)


# ── Category Detail / Filter ─────────────────────
@app.route('/category/<int:category_id>')
@app.route('/category/<int:category_id>/<string:slug>')
def category_detail(category_id, slug=None):
    category = Category.query.get_or_404(category_id)
    from utils.seo import slugify
    expected_slug = category.slug or slugify(category.name)
    if slug != expected_slug:
        return redirect(url_for('category_detail', category_id=category.id, slug=expected_slug), code=301)
    
    page         = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    tag_name     = request.args.get('tag', '').strip()

    query = Blog.query.options(
        db.joinedload(Blog.author),
        db.joinedload(Blog.category)
    ).filter_by(is_blocked=False, category_id=category_id)

    if search_query:
        query = query.filter(
            Blog.title.contains(search_query) | Blog.content.contains(search_query)
        )
    if tag_name:
        query = query.join(Blog.tags).filter(Tag.name == tag_name.lower())

    blogs      = query.order_by(Blog.date_posted.desc()).paginate(page=page, per_page=9)
    categories = Category.query.all()

    # Trending: top 5 by views
    trending = Blog.query.options(
        db.joinedload(Blog.author),
        db.joinedload(Blog.category)
    ).filter_by(is_blocked=False).order_by(Blog.views.desc()).limit(5).all()

    return render_template('index.html', blogs=blogs, categories=categories,
                           trending=trending, search_query=search_query,
                           active_cat=category_id, active_tag=tag_name)


# ── Auth ────────────────────────────────────────
# ── Profile ─────────────────────────────────────
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm(current_user.username, current_user.email)
    if form.validate_on_submit():
        if form.picture.data:
            pic_url, pic_public_id = save_profile_picture(form.picture.data)
            if pic_url:
                if current_user.profile_image_public_id:
                    delete_image(current_user.profile_image_public_id)
                current_user.image_file = pic_url
                current_user.profile_image_public_id = pic_public_id
        current_user.username = form.username.data
        current_user.email    = form.email.data
        current_user.bio      = form.bio.data
        db.session.commit()
        log_activity("Updated profile", target_type="User", target_id=current_user.id, details="Updated account settings")
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data    = current_user.email
        form.bio.data      = current_user.bio

    # Stats for profile page
    total_likes = current_user.total_likes_received()
    total_posts = len(current_user.blogs)
    bookmarked_blogs = (Blog.query
                        .join(Bookmark)
                        .filter(Bookmark.user_id == current_user.id)
                        .order_by(Bookmark.date_saved.desc())
                        .all())

    # Recent activities
    recent_activities = (ActivityLog.query
                         .filter(ActivityLog.user_id == current_user.id)
                         .order_by(ActivityLog.timestamp.desc())
                         .limit(10)
                         .all())

    # Follower stats
    followers_count = current_user.followers.count()
    following_count = current_user.followed.count()

    return render_template('profile.html', title='Profile', form=form,
                           total_likes=total_likes, total_posts=total_posts,
                           bookmarked_blogs=bookmarked_blogs,
                           recent_activities=recent_activities,
                           followers_count=followers_count,
                           following_count=following_count)


# ── Serve uploaded profile pictures ─────────────
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ── Dashboard ────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    blogs = Blog.query.filter_by(author=current_user).order_by(Blog.date_posted.desc()).all()
    return render_template('dashboard.html', blogs=blogs)


# ── Admin Dashboard ──────────────────────────────
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    users      = User.query.all()
    blogs      = Blog.query.order_by(Blog.date_posted.desc()).all()
    categories = Category.query.all()
    comments   = Comment.query.order_by(Comment.date_posted.desc()).all()
    stats = {
        'total_users':      len(users),
        'total_blogs':      len(blogs),
        'total_categories': len(categories),
        'total_comments':   len(comments),
    }
    return render_template('admin_dashboard.html', users=users, blogs=blogs,
                           categories=categories, comments=comments, stats=stats)


@app.route('/admin/delete_category/<int:category_id>', methods=['POST'])
@login_required
def admin_delete_category(category_id):
    if not current_user.is_admin:
        abort(403)
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def admin_delete_comment(comment_id):
    if not current_user.is_admin:
        abort(403)
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot delete an admin user.', 'danger')
        return redirect(url_for('admin_dashboard'))
    Blog.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_blog/<int:blog_id>', methods=['POST'])
@login_required
def admin_delete_blog(blog_id):
    if not current_user.is_admin:
        abort(403)
    blog = Blog.query.get_or_404(blog_id)
    db.session.delete(blog)
    db.session.commit()
    flash('Blog deleted by admin.', 'success')
    return redirect(url_for('admin_dashboard'))


# ── Create / Edit Blog ───────────────────────────
@app.route('/blog/new', methods=['GET', 'POST'])
@login_required
def create_blog():
    form = BlogForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        safe_content = sanitize_html(form.content.data)
        
        # AI TAG GENERATOR: Auto-generate if tags are empty
        tags_data = form.tags.data
        if not tags_data or not tags_data.strip():
            from services.ai_service import generate_tags
            ai_tags = generate_tags(safe_content, num_tags=5)
            tags_data = ', '.join(ai_tags)
            
        # AI SENTIMENT ANALYSIS
        from services.ai_service import analyze_sentiment
        sentiment = analyze_sentiment(safe_content)
            
        blog = Blog(
            title       = form.title.data,
            content     = safe_content,
            author      = current_user,
            category_id = form.category.data,
            sentiment   = sentiment
        )
        
        if form.cover_image.data:
            cover_res = upload_image(form.cover_image.data, folder="techinsights/covers")
            if cover_res:
                blog.cover_image = cover_res['url']
                blog.image_public_id = cover_res['public_id']

        blog.tags = process_tags(tags_data)
        db.session.add(blog)
        db.session.commit()
        log_activity("Created blog", target_type="Blog", target_id=blog.id, details=blog.title)
        cache.delete('api_stats')
        flash('Your blog has been published!', 'success')
        from utils.seo import slugify
        return redirect(url_for('blog_detail', blog_id=blog.id, slug=blog.slug or slugify(blog.title)))
    return render_template('create_blog.html', title='New Blog',
                           form=form, legend='Create New Blog')


@app.route('/blog/<int:blog_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_blog(blog_id):
    blog = Blog.query.options(db.joinedload(Blog.category)).get_or_404(blog_id)
    if blog.author != current_user and not current_user.is_admin:
        abort(403)
    form = BlogForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        blog.title       = form.title.data
        blog.content     = sanitize_html(form.content.data)
        blog.category_id = form.category.data
        blog.tags        = process_tags(form.tags.data)
        
        if form.cover_image.data:
            cover_res = upload_image(form.cover_image.data, folder="techinsights/covers")
            if cover_res:
                if blog.image_public_id:
                    delete_image(blog.image_public_id)
                blog.cover_image = cover_res['url']
                blog.image_public_id = cover_res['public_id']

        db.session.commit()
        log_activity("Updated blog", target_type="Blog", target_id=blog.id, details=blog.title)
        cache.delete('api_stats')
        flash('Your blog has been updated!', 'success')
        from utils.seo import slugify
        return redirect(url_for('blog_detail', blog_id=blog.id, slug=blog.slug or slugify(blog.title)))
    elif request.method == 'GET':
        form.title.data   = blog.title
        form.content.data = blog.content
        form.category.data = blog.category_id
        form.tags.data    = ', '.join([t.name for t in blog.tags])
    return render_template('create_blog.html', title='Edit Blog',
                           form=form, legend='Edit Blog', blog=blog)


# ── Blog Detail ──────────────────────────────────
@app.route('/blog/<int:blog_id>', methods=['GET', 'POST'])
@app.route('/blog/<int:blog_id>/<string:slug>', methods=['GET', 'POST'])
def blog_detail(blog_id, slug=None):
    blog = Blog.query.options(
        db.joinedload(Blog.author),
        db.joinedload(Blog.category)
    ).get_or_404(blog_id)

    from utils.seo import slugify
    expected_slug = blog.slug or slugify(blog.title)
    if request.method == 'GET' and slug != expected_slug:
        return redirect(url_for('blog_detail', blog_id=blog.id, slug=expected_slug), code=301)

    # ── Unique view counter (session-based) ────────
    from flask import session
    if 'viewed_blogs' not in session:
        session['viewed_blogs'] = []
    viewed_blogs = list(session['viewed_blogs'])
    if blog_id not in viewed_blogs:
        blog.views += 1
        db.session.commit()
        viewed_blogs.append(blog_id)
        session['viewed_blogs'] = viewed_blogs
        session.modified = True

    form = CommentForm()
    if form.validate_on_submit() and current_user.is_authenticated:
        parent_id = form.parent_id.data or None
        # Validate parent comment belongs to same blog
        if parent_id:
            parent_comment = Comment.query.get(parent_id)
            if not parent_comment or parent_comment.blog_id != blog_id:
                parent_id = None
        comment = Comment(
            content   = form.content.data,
            author    = current_user,
            blog      = blog,
            parent_id = parent_id
        )
        db.session.add(comment)
        db.session.commit()
        
        # Log activity
        log_activity("Commented on blog", target_type="Blog", target_id=blog.id, details=comment.content[:50])
        
        # Send Notification
        if blog.author != current_user:
            from services.socket_service import send_notification
            send_notification(
                receiver_id=blog.author.id,
                sender_id=current_user.id,
                notification_type='comment',
                message=f"{current_user.username} commented on your blog '{blog.title[:20]}...'",
                link_url=url_for('blog_detail', blog_id=blog.id, slug=expected_slug)
            )

        flash('Comment posted!', 'success')
        return redirect(url_for('blog_detail', blog_id=blog.id, slug=expected_slug) + '#comments')

    has_liked      = False
    has_bookmarked = False
    liked_comments = set()
    if current_user.is_authenticated:
        has_liked = Like.query.filter_by(
            user_id=current_user.id, blog_id=blog.id).first() is not None
        has_bookmarked = Bookmark.query.filter_by(
            user_id=current_user.id, blog_id=blog.id).first() is not None
        liked_comments = {
            cl.comment_id for cl in CommentLike.query.filter_by(user_id=current_user.id).all()
        }

    # Only top-level comments (no parent) - eager load their author
    top_comments = (Comment.query
                    .options(db.joinedload(Comment.author))
                    .filter_by(blog_id=blog_id, parent_id=None)
                    .order_by(Comment.date_posted.asc())
                    .all())

    # Recommended: AI Recommendation Engine (Content-based TF-IDF)
    all_blogs = Blog.query.all()
    from services.recommendation_engine import get_recommendations
    recommended = get_recommendations(blog.id, all_blogs, top_n=4)
    # Fallback to category based if ML fails/is warming up
    if not recommended:
        recommended = (Blog.query
                       .options(db.joinedload(Blog.author))
                       .filter(Blog.category_id == blog.category_id, Blog.id != blog.id)
                       .order_by(Blog.views.desc())
                       .limit(4).all())

    # Generate JSON-LD Schema
    from utils.seo import generate_json_ld
    schema_json_ld = generate_json_ld(blog)

    return render_template(
        'blog_detail.html', title=blog.title, blog=blog,
        form=form, has_liked=has_liked, has_bookmarked=has_bookmarked,
        top_comments=top_comments, liked_comments=liked_comments,
        recommended=recommended, schema_json_ld=schema_json_ld
    )


# ── Delete Blog ──────────────────────────────────
@app.route('/blog/<int:blog_id>/delete', methods=['POST'])
@login_required
def delete_blog(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    if blog.author != current_user and not current_user.is_admin:
        abort(403)
        
    if blog.image_public_id:
        delete_image(blog.image_public_id)
        
    blog_title = blog.title
    db.session.delete(blog)
    db.session.commit()
    log_activity("Deleted blog", target_type="Blog", target_id=blog_id, details=blog_title)
    cache.delete('api_stats')
    flash('Blog deleted.', 'success')
    return redirect(url_for('home'))


# ── Like / Unlike Blog (AJAX) ────────────────────
@app.route('/like/<int:blog_id>', methods=['POST'])
@login_required
def like_action(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    like = Like.query.filter_by(user_id=current_user.id, blog_id=blog.id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        log_activity("Unliked blog", target_type="Blog", target_id=blog.id, details=blog.title)
        return jsonify({'status': 'unliked', 'likes_count': len(blog.likes)})
    else:
        db.session.add(Like(user_id=current_user.id, blog_id=blog.id))
        db.session.commit()
        log_activity("Liked blog", target_type="Blog", target_id=blog.id, details=blog.title)
        
        # Send Notification
        if blog.author != current_user:
            from services.socket_service import send_notification
            from utils.seo import slugify
            send_notification(
                receiver_id=blog.author.id,
                sender_id=current_user.id,
                notification_type='like',
                message=f"{current_user.username} liked your blog '{blog.title[:20]}...'",
                link_url=url_for('blog_detail', blog_id=blog.id, slug=blog.slug or slugify(blog.title))
            )
            
        return jsonify({'status': 'liked', 'likes_count': len(blog.likes)})


# ── Bookmark / Unbookmark (AJAX) ─────────────────
@app.route('/bookmark/<int:blog_id>', methods=['POST'])
@login_required
def bookmark_action(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    bookmark = Bookmark.query.filter_by(user_id=current_user.id, blog_id=blog.id).first()
    if bookmark:
        db.session.delete(bookmark)
        db.session.commit()
        log_activity("Removed bookmark", target_type="Blog", target_id=blog.id, details=blog.title)
        return jsonify({'status': 'removed'})
    else:
        db.session.add(Bookmark(user_id=current_user.id, blog_id=blog.id))
        db.session.commit()
        log_activity("Bookmarked blog", target_type="Blog", target_id=blog.id, details=blog.title)
        
        # Send Notification
        if blog.author != current_user:
            from services.socket_service import send_notification
            from utils.seo import slugify
            send_notification(
                receiver_id=blog.author.id,
                sender_id=current_user.id,
                notification_type='bookmark',
                message=f"{current_user.username} bookmarked your blog '{blog.title[:20]}...'",
                link_url=url_for('blog_detail', blog_id=blog.id, slug=blog.slug or slugify(blog.title))
            )

        return jsonify({'status': 'saved'})


# ── Follow / Unfollow Actions (AJAX) ─────────────
@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow_user(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        return jsonify({'error': 'You cannot follow yourself.'}), 400
    
    if current_user.is_following(user):
        return jsonify({'error': 'You are already following this user.'}), 400
        
    current_user.follow(user)
    db.session.commit()
    
    # Log activity
    log_activity("Followed user", target_type="User", target_id=user.id, details=user.username)
    
    # Send Notification
    from services.socket_service import send_notification
    send_notification(
        receiver_id=user.id,
        sender_id=current_user.id,
        notification_type='follow',
        message=f"{current_user.username} started following you!",
        link_url=url_for('user_profile', username=current_user.username)
    )
    
    return jsonify({
        'status': 'followed',
        'username': user.username,
        'followers_count': user.followers.count(),
        'following_count': user.followed.count()
    })


@app.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow_user(user_id):
    user = User.query.get_or_404(user_id)
    if not current_user.is_following(user):
        return jsonify({'error': 'You are not following this user.'}), 400
        
    current_user.unfollow(user)
    db.session.commit()
    
    # Log activity
    log_activity("Unfollowed user", target_type="User", target_id=user.id, details=user.username)
    
    return jsonify({
        'status': 'unfollowed',
        'username': user.username,
        'followers_count': user.followers.count(),
        'following_count': user.followed.count()
    })


# ── Saved Posts Page ─────────────────────────────
@app.route('/saved')
@login_required
def saved_posts():
    bookmarked_blogs = (Blog.query
                        .options(db.joinedload(Blog.author), db.joinedload(Blog.category))
                        .join(Bookmark)
                        .filter(Bookmark.user_id == current_user.id)
                        .order_by(Bookmark.date_saved.desc())
                        .all())
    return render_template('saved_posts.html', title='Saved Posts',
                           bookmarked_blogs=bookmarked_blogs)


# ── Comment Actions ──────────────────────────────
@app.route('/blog/<int:blog_id>/comment', methods=['POST'])
@login_required
def create_comment_ajax(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    form = CommentForm()
    if form.validate_on_submit():
        parent_id = form.parent_id.data or None
        if parent_id:
            parent_comment = Comment.query.get(parent_id)
            if not parent_comment or parent_comment.blog_id != blog_id:
                return jsonify({'error': 'Invalid parent comment'}), 400
        
        comment = Comment(
            content=form.content.data,
            author=current_user,
            blog_id=blog_id,
            parent_id=parent_id
        )
        db.session.add(comment)
        db.session.commit()
        
        # Log activity
        log_activity("Commented on blog", target_type="Blog", target_id=blog_id, details=comment.content[:50])
        
        # Send Notification
        if blog.author != current_user:
            from services.socket_service import send_notification
            from utils.seo import slugify
            send_notification(
                receiver_id=blog.author.id,
                sender_id=current_user.id,
                notification_type='comment',
                message=f"{current_user.username} commented on your blog '{blog.title[:20]}...'",
                link_url=url_for('blog_detail', blog_id=blog.id, slug=blog.slug or slugify(blog.title))
            )
            
        liked_comments = {
            cl.comment_id for cl in CommentLike.query.filter_by(user_id=current_user.id).all()
        }
        
        comment_html = render_template('partials/_comment_single.html', comment=comment, liked_comments=liked_comments)
        comments_count = Comment.query.filter_by(blog_id=blog_id).count()
        
        return jsonify({
            'success': True,
            'comment_html': comment_html,
            'parent_id': parent_id,
            'comments_count': comments_count
        })
        
    return jsonify({'error': 'Validation failed', 'errors': form.errors}), 400


@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    blog_id = comment.blog_id
    db.session.delete(comment)
    db.session.commit()
    
    log_activity("Deleted comment", target_type="Comment", target_id=comment_id)
    comments_count = Comment.query.filter_by(blog_id=blog_id).count()
    
    return jsonify({
        'status': 'deleted',
        'comments_count': comments_count
    })


@app.route('/comment/<int:comment_id>/edit', methods=['POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user:
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    new_content = data.get('content', '').strip()
    if not new_content:
        return jsonify({'error': 'Content cannot be empty'}), 400
    comment.content = new_content
    db.session.commit()
    return jsonify({'status': 'updated', 'content': comment.content})


# ── Like / Unlike Comment (AJAX) ─────────────────
@app.route('/comment_like/<int:comment_id>', methods=['POST'])
@login_required
def comment_like_action(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    cl = CommentLike.query.filter_by(
        user_id=current_user.id, comment_id=comment_id).first()
    if cl:
        db.session.delete(cl)
        db.session.commit()
        return jsonify({'status': 'unliked',
                        'likes_count': len(comment.comment_likes)})
    else:
        db.session.add(CommentLike(user_id=current_user.id, comment_id=comment_id))
        db.session.commit()
        return jsonify({'status': 'liked',
                        'likes_count': len(comment.comment_likes)})


# ── Public User Profile ──────────────────────────
@app.route('/user/<string:username>')
def user_profile(username):
    user  = User.query.filter_by(username=username).first_or_404()
    blogs = Blog.query.options(db.joinedload(Blog.category)).filter_by(author=user).order_by(Blog.date_posted.desc()).all()
    
    followers_count = user.followers.count()
    following_count = user.followed.count()
    
    is_following = False
    if current_user.is_authenticated:
        is_following = current_user.is_following(user)
        
    return render_template('user_profile.html', title=f'{user.username}\'s Profile',
                           user=user, blogs=blogs,
                           followers_count=followers_count,
                           following_count=following_count,
                           is_following=is_following)


# ── Tag page ─────────────────────────────────────
@app.route('/tag/<string:tag_name>')
def tag_page(tag_name):
    tag   = Tag.query.filter_by(name=tag_name.lower()).first_or_404()
    blogs = Blog.query.options(db.joinedload(Blog.author), db.joinedload(Blog.category)).join(Blog.tags).filter(Tag.id == tag.id).order_by(Blog.date_posted.desc()).all()
    return render_template('tag_page.html', title=f'#{tag_name}',
                           tag=tag, blogs=blogs)


# ── Image Upload for Quill Editor ────────────────
@app.route('/upload_image', methods=['POST'])
@login_required
def upload_quill_image():
    """Handle inline image uploads from Quill editor."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return jsonify({'error': 'File type not allowed'}), 400
    filename = secrets.token_hex(12) + '.' + ext
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    image_url = url_for('uploaded_file', filename=filename)
    return jsonify({'url': image_url})


# ── AI API Endpoints ──────────────────────────────
@app.route('/api/blog/<int:blog_id>/summarize', methods=['POST'])
@login_required
def api_summarize_blog(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    if blog.summary:
        return jsonify({'summary': blog.summary})
        
    from services.ai_service import generate_summary
    # Ensure csrf valid
    summary = generate_summary(blog.content)
    if summary and not summary.startswith("Error") and not summary.startswith("AI Summarization unavailable"):
        blog.summary = summary
        db.session.commit()
    
    return jsonify({'summary': summary})


@app.route('/api/blog/generate_title', methods=['POST'])
@login_required
def api_generate_title():
    data = request.get_json()
    content = data.get('content', '')
    from services.ai_service import generate_title
    title = generate_title(content)
    return jsonify({'title': title})


# ── Error Handlers ────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500



# ── Stats API (for hero counter animation) ────────
@app.route('/api/stats')
@cache.cached(timeout=300, key_prefix='api_stats')
def api_stats():
    total_views = db.session.query(db.func.sum(Blog.views)).scalar() or 0
    return jsonify({
        'posts': Blog.query.count(),
        'users': User.query.count(),
        'views': total_views,
    })


# ── robots.txt ───────────────────────────────────
@app.route('/robots.txt')
def robots():
    lines = [
        "User-agent: *",
        "Disallow: /admin_dashboard",
        "Disallow: /dashboard",
        "Disallow: /profile",
        "Disallow: /saved",
        "Disallow: /api/",
        f"Sitemap: {url_for('sitemap', _external=True)}"
    ]
    return Response("\n".join(lines), mimetype="text/plain")


# ── sitemap.xml ──────────────────────────────────
@app.route('/sitemap.xml')
def sitemap():
    pages = []
    
    # 1. Main Static Pages
    pages.append({
        'loc': url_for('home', _external=True),
        'changefreq': 'daily',
        'priority': '1.0'
    })
    
    # 2. Categories
    categories = Category.query.all()
    from utils.seo import slugify
    for cat in categories:
        pages.append({
            'loc': url_for('category_detail', category_id=cat.id, slug=cat.slug or slugify(cat.name), _external=True),
            'changefreq': 'weekly',
            'priority': '0.8'
        })
        
    # 3. Blog posts
    blogs = Blog.query.filter_by(is_blocked=False).all()
    for blog in blogs:
        lastmod = blog.date_posted.strftime('%Y-%m-%d') if blog.date_posted else None
        pages.append({
            'loc': url_for('blog_detail', blog_id=blog.id, slug=blog.slug or slugify(blog.title), _external=True),
            'lastmod': lastmod,
            'changefreq': 'monthly',
            'priority': '0.6'
        })
        
    # 4. Public User Profiles
    users = User.query.filter_by(is_banned=False).all()
    for user in users:
        pages.append({
            'loc': url_for('user_profile', username=user.username, _external=True),
            'changefreq': 'weekly',
            'priority': '0.4'
        })
        
    sitemap_xml = render_template('seo/sitemap.xml', pages=pages)
    return Response(sitemap_xml, mimetype="application/xml")


if __name__ == '__main__':
    socketio.run(app, debug=True)

