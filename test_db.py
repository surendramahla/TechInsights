from app import app, db
from models import User, Blog

with app.app_context():
    # Find a user or create one
    user = User.query.first()
    if not user:
        print("No users in db")
    else:
        print(f"User: {user}")
        try:
            blogs = Blog.query.filter_by(author=user).all()
            print(f"Blogs by author: {blogs}")
        except Exception as e:
            print(f"Error filtering by author: {e}")
