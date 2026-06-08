from flask import render_template, url_for, flash, redirect, request, jsonify, abort
from flask_login import current_user, login_required
from functools import wraps
from extensions import db
from models import User, Blog, Comment, ActivityLog
from . import admin_bp
from utils.helpers import log_activity
from datetime import datetime, timedelta

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.before_request
@admin_required
def before_request():
    pass

@admin_bp.route('/')
def dashboard():
    total_users = User.query.count()
    total_blogs = Blog.query.count()
    total_comments = Comment.query.count()
    total_views = db.session.query(db.func.sum(Blog.views)).scalar() or 0
    active_users = User.query.filter_by(account_status='active', is_banned=False).count()
    
    # Recent items
    recent_activity = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(10).all()
    trending_blogs = Blog.query.order_by(Blog.views.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_blogs=total_blogs,
                           total_comments=total_comments,
                           total_views=total_views,
                           active_users=active_users,
                           recent_activity=recent_activity,
                           trending_blogs=trending_blogs)

@admin_bp.route('/users')
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    query = User.query
    if search:
        query = query.filter(User.username.ilike(f'%{search}%') | User.email.ilike(f'%{search}%'))
    users = query.order_by(User.date_joined.desc()).paginate(page=page, per_page=15)
    return render_template('admin/users.html', users=users, search=search)

@admin_bp.route('/user/<int:user_id>/ban', methods=['POST'])
def toggle_ban(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot ban yourself.'}), 400
    user.is_banned = not user.is_banned
    user.account_status = 'banned' if user.is_banned else 'active'
    db.session.commit()
    log_activity(f"{'Banned' if user.is_banned else 'Unbanned'} user", target_type='User', target_id=user.id, details=user.username)
    return jsonify({'success': True, 'is_banned': user.is_banned})

@admin_bp.route('/user/<int:user_id>/role', methods=['POST'])
def toggle_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot change your own role.'}), 400
    user.is_admin = not user.is_admin
    db.session.commit()
    log_activity(f"{'Promoted to Admin' if user.is_admin else 'Removed Admin'} user", target_type='User', target_id=user.id, details=user.username)
    return jsonify({'success': True, 'is_admin': user.is_admin})

@admin_bp.route('/blogs')
def blogs():
    page = request.args.get('page', 1, type=int)
    blogs = Blog.query.order_by(Blog.date_posted.desc()).paginate(page=page, per_page=15)
    return render_template('admin/blogs.html', blogs=blogs)

@admin_bp.route('/blog/<int:blog_id>/block', methods=['POST'])
def toggle_block(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    blog.is_blocked = not blog.is_blocked
    db.session.commit()
    log_activity(f"{'Blocked' if blog.is_blocked else 'Unblocked'} blog", target_type='Blog', target_id=blog.id, details=blog.title)
    return jsonify({'success': True, 'is_blocked': blog.is_blocked})

@admin_bp.route('/blog/<int:blog_id>/feature', methods=['POST'])
def toggle_feature(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    blog.is_featured = not blog.is_featured
    db.session.commit()
    log_activity(f"{'Featured' if blog.is_featured else 'Unfeatured'} blog", target_type='Blog', target_id=blog.id, details=blog.title)
    return jsonify({'success': True, 'is_featured': blog.is_featured})

@admin_bp.route('/comments')
def comments():
    page = request.args.get('page', 1, type=int)
    comments = Comment.query.order_by(Comment.date_posted.desc()).paginate(page=page, per_page=20)
    return render_template('admin/comments.html', comments=comments)

@admin_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    log_activity("Deleted comment", target_type='Comment', target_id=comment_id)
    return jsonify({'success': True})

@admin_bp.route('/activity')
def activity():
    page = request.args.get('page', 1, type=int)
    activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).paginate(page=page, per_page=30)
    return render_template('admin/activity.html', activities=activities)

# Analytics data endpoint for Chart.js
@admin_bp.route('/api/analytics')
def analytics_data():
    # Last 6 months user growth placeholder (Needs group_by normally)
    # For simplicity, returning mock historical data that can be replaced by real grouping
    labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    users_data = [50, 100, 200, 400, 600, User.query.count()]
    blogs_data = [10, 25, 50, 80, 150, Blog.query.count()]
    return jsonify({
        'labels': labels,
        'users': users_data,
        'blogs': blogs_data
    })
