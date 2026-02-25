from flask import Flask, render_template, url_for, flash, redirect, request, abort
from extensions import db, bcrypt, login_manager
from forms import RegistrationForm, LoginForm, BlogForm, CommentForm, UpdateProfileForm
from models import User, Blog, Comment, Like, Category
from flask_login import login_user, current_user, logout_user, login_required
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '5791628bb0b13ce0c676dfde280ba245'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

with app.app_context():
    db.create_all()
    # create default admin if none exists
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')
        admin_user = User(username='admin', email='admin@example.com', password=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
    
    # create default categories
    default_categories = ['Technology', 'Lifestyle', 'Education', 'Entertainment', 'Others']
    if Category.query.count() == 0:
        for cat_name in default_categories:
            cat = Category(name=cat_name)
            db.session.add(cat)
        db.session.commit()

@app.route("/")
@app.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q')
    if search_query:
        blogs = Blog.query.filter(Blog.title.contains(search_query) | Blog.content.contains(search_query)).order_by(Blog.date_posted.desc()).paginate(page=page, per_page=10)
    else:
        blogs = Blog.query.order_by(Blog.date_posted.desc()).paginate(page=page, per_page=10)
    return render_template('index.html', blogs=blogs, search_query=search_query)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm(current_user.username, current_user.email)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
    return render_template('profile.html', title='Profile', form=form)

@app.route("/dashboard")
@login_required
def dashboard():
    blogs = Blog.query.filter_by(author=current_user).order_by(Blog.date_posted.desc()).all()
    return render_template('dashboard.html', blogs=blogs)

@app.route("/admin_dashboard")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    users = User.query.all()
    blogs = Blog.query.order_by(Blog.date_posted.desc()).all()
    return render_template('admin_dashboard.html', users=users, blogs=blogs)

@app.route("/admin/delete_user/<int:user_id>", methods=['POST'])
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
    flash('User has been deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/delete_blog/<int:blog_id>", methods=['POST'])
@login_required
def admin_delete_blog(blog_id):
    if not current_user.is_admin:
        abort(403)
    blog = Blog.query.get_or_404(blog_id)
    db.session.delete(blog)
    db.session.commit()
    flash('Blog has been deleted by admin.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/blog/new", methods=['GET', 'POST'])
@login_required
def create_blog():
    form = BlogForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    # add a default 'None' option if needed, but we'll assume they must pick one since default db has them
    if form.validate_on_submit():
        blog = Blog(title=form.title.data, content=form.content.data, author=current_user, category_id=form.category.data)
        db.session.add(blog)
        db.session.commit()
        flash('Your blog has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_blog.html', title='New Blog', form=form, legend='Create New Blog')

@app.route("/blog/<int:blog_id>", methods=['GET', 'POST'])
def blog_detail(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    # Increment view count
    blog.views += 1
    db.session.commit()

    form = CommentForm()
    if form.validate_on_submit() and current_user.is_authenticated:
        comment = Comment(content=form.content.data, author=current_user, blog=blog)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been posted!', 'success')
        return redirect(url_for('blog_detail', blog_id=blog.id))
    
    has_liked = False
    if current_user.is_authenticated:
        has_liked = Like.query.filter_by(user_id=current_user.id, blog_id=blog.id).first() is not None

    return render_template('blog_detail.html', title=blog.title, blog=blog, form=form, has_liked=has_liked)

@app.route("/like/<int:blog_id>", methods=['POST'])
@login_required
def like_action(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    like = Like.query.filter_by(user_id=current_user.id, blog_id=blog.id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        return {'status': 'unliked', 'likes_count': len(blog.likes)}
    else:
        new_like = Like(user_id=current_user.id, blog_id=blog.id)
        db.session.add(new_like)
        db.session.commit()
        return {'status': 'liked', 'likes_count': len(blog.likes)}

@app.route("/delete_comment/<int:comment_id>", methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user and not current_user.is_admin:
        abort(403)
    blog_id = comment.blog_id
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted.', 'info')
    return redirect(url_for('blog_detail', blog_id=blog_id))

@app.route("/blog/<int:blog_id>/delete", methods=['POST'])
@login_required
def delete_blog(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    if blog.author != current_user and not current_user.is_admin:
        abort(403)
    db.session.delete(blog)
    db.session.commit()
    flash('Blog has been deleted.', 'success')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
