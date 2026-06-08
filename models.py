from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ──────────────────────────────────────────────
# Blog ↔ Tag  many-to-many association table
# ──────────────────────────────────────────────
blog_tags = db.Table(
    'blog_tags',
    db.Column('blog_id', db.Integer, db.ForeignKey('blog.id'), primary_key=True),
    db.Column('tag_id',  db.Integer, db.ForeignKey('tag.id'),  primary_key=True)
)

# ──────────────────────────────────────────────
# User Followers many-to-many association table
# ──────────────────────────────────────────────
followers_association = db.Table(
    'followers_association',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

# ──────────────────────────────────────────────
# User Model
# ──────────────────────────────────────────────
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(20),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(200), nullable=False, default='default.jpg')
    profile_image_public_id = db.Column(db.String(200), nullable=True)
    password   = db.Column(db.String(60),  nullable=False)
    is_admin   = db.Column(db.Boolean, default=False)
    is_banned  = db.Column(db.Boolean, default=False)
    account_status = db.Column(db.String(20), default='active')
    bio        = db.Column(db.Text, nullable=True)
    google_id  = db.Column(db.String(120), unique=True, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    last_login  = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(100), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    # Timestamps
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    blogs         = db.relationship('Blog',        backref='author',    lazy=True)
    comments      = db.relationship('Comment',     backref='author',    lazy=True)
    likes         = db.relationship('Like',        backref='user',      lazy=True)
    bookmarks     = db.relationship('Bookmark',    backref='user',      lazy=True)
    comment_likes = db.relationship('CommentLike', backref='user',      lazy=True)

    # Followers many-to-many self-referential
    followed = db.relationship(
        'User', secondary=followers_association,
        primaryjoin=(followers_association.c.follower_id == id),
        secondaryjoin=(followers_association.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    )

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers_association.c.followed_id == user.id).count() > 0

    def total_likes_received(self):
        """Count all likes across all blogs authored by this user."""
        total = 0
        for blog in self.blogs:
            total += len(blog.likes)
        return total

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"


# ──────────────────────────────────────────────
# Category Model
# ──────────────────────────────────────────────
class Category(db.Model):
    __tablename__ = 'category'
    id    = db.Column(db.Integer, primary_key=True)
    name  = db.Column(db.String(50), nullable=False, unique=True)
    slug  = db.Column(db.String(100), unique=True, nullable=True, index=True)
    blogs = db.relationship('Blog', backref='category', lazy=True)

    def __repr__(self):
        return f"Category('{self.name}')"


# ──────────────────────────────────────────────
# Tag Model
# ──────────────────────────────────────────────
class Tag(db.Model):
    __tablename__ = 'tag'
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return f"Tag('{self.name}')"


# ──────────────────────────────────────────────
# Blog Model
# ──────────────────────────────────────────────
class Blog(db.Model):
    __tablename__ = 'blog'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    slug        = db.Column(db.String(255), unique=True, nullable=True, index=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    cover_image = db.Column(db.String(255), nullable=True, default='default_cover.jpg')
    image_public_id = db.Column(db.String(200), nullable=True)
    content     = db.Column(db.Text, nullable=False)   # stores Quill HTML
    views       = db.Column(db.Integer, default=0, index=True)
    summary     = db.Column(db.Text, nullable=True)      # AI generated summary
    sentiment   = db.Column(db.String(50), nullable=True) # AI detected tone
    is_blocked  = db.Column(db.Boolean, default=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    moderation_reason = db.Column(db.String(200), nullable=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)

    # Tags many-to-many
    tags = db.relationship('Tag', secondary=blog_tags, backref=db.backref('blogs', lazy='dynamic'))

    # Relationships with cascades
    comments  = db.relationship('Comment',  backref='blog', lazy=True, cascade='all, delete-orphan')
    likes     = db.relationship('Like',     backref='blog', lazy=True, cascade='all, delete-orphan')
    bookmarks = db.relationship('Bookmark', backref='blog', lazy=True, cascade='all, delete-orphan')

    def read_time(self):
        """Estimate reading time based on ~200 words/min average."""
        import re
        text = re.sub(r'<[^>]+>', '', self.content or '')
        words = len(text.split())
        minutes = max(1, round(words / 200))
        return minutes

    def excerpt(self, chars=200):
        """Return a plain-text excerpt from HTML content."""
        import re
        text = re.sub(r'<[^>]+>', '', self.content or '')
        return text[:chars] + '...' if len(text) > chars else text

    def __repr__(self):
        return f"Blog('{self.title}', '{self.date_posted}')"


# ──────────────────────────────────────────────
# Comment Model  (supports nested replies via parent_id)
# ──────────────────────────────────────────────
class Comment(db.Model):
    __tablename__ = 'comment'
    id          = db.Column(db.Integer, primary_key=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    content     = db.Column(db.Text, nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'),   nullable=False)
    blog_id     = db.Column(db.Integer, db.ForeignKey('blog.id'),   nullable=False)
    parent_id   = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)  # self-referencing
    is_reported = db.Column(db.Boolean, default=False)

    # Self-referential relationship for nested replies
    replies = db.relationship(
        'Comment',
        backref=db.backref('parent', remote_side='Comment.id'),
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    # Comment likes
    comment_likes = db.relationship('CommentLike', backref='comment', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"Comment('{self.content[:30]}', user={self.user_id})"


# ──────────────────────────────────────────────
# Like Model  (blog likes)
# ──────────────────────────────────────────────
class Like(db.Model):
    __tablename__ = 'like'
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    # Unique constraint: one like per user per blog
    __table_args__ = (db.UniqueConstraint('user_id', 'blog_id', name='unique_blog_like'),)


# ──────────────────────────────────────────────
# CommentLike Model
# ──────────────────────────────────────────────
class CommentLike(db.Model):
    __tablename__ = 'comment_like'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'),    nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='unique_comment_like'),)


# ──────────────────────────────────────────────
# Bookmark Model
# ──────────────────────────────────────────────
class Bookmark(db.Model):
    __tablename__ = 'bookmark'
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)
    date_saved = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'blog_id', name='unique_bookmark'),)

# ──────────────────────────────────────────────
# ActivityLog Model
# ──────────────────────────────────────────────
class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action      = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)
    target_id   = db.Column(db.Integer, nullable=True)
    details     = db.Column(db.Text, nullable=True)
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='activities', lazy=True)
    
    def __repr__(self):
        return f"ActivityLog('{self.action}', '{self.timestamp}')"

# ──────────────────────────────────────────────
# Media Model
# ──────────────────────────────────────────────
class Media(db.Model):
    __tablename__ = 'media'
    id          = db.Column(db.Integer, primary_key=True)
    file_name   = db.Column(db.String(255), nullable=False)
    file_url    = db.Column(db.String(500), nullable=False)
    public_id   = db.Column(db.String(200), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    user = db.relationship('User', backref='media_uploads', lazy=True)

    def __repr__(self):
        return f"Media('{self.file_name}', '{self.upload_date}')"

# ──────────────────────────────────────────────
# Notification Model
# ──────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'notification'
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    message     = db.Column(db.String(255), nullable=False)
    link_url    = db.Column(db.String(255), nullable=True)
    is_read     = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref=db.backref('notifications', lazy='dynamic', cascade='all, delete-orphan'))
    sender   = db.relationship('User', foreign_keys=[sender_id])

    def __repr__(self):
        return f"Notification('{self.notification_type}', to={self.receiver_id}, read={self.is_read})"

# ──────────────────────────────────────────────
# Chat Models (Conversation & Message)
# ──────────────────────────────────────────────
class Conversation(db.Model):
    __tablename__ = 'conversation'
    id              = db.Column(db.Integer, primary_key=True)
    user1_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])
    
    # constraint to ensure uniqueness of pairs (could be done via app logic or sorted IDs)

class Message(db.Model):
    __tablename__ = 'message'
    id              = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    sender_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    timestamp       = db.Column(db.DateTime, default=datetime.utcnow)
    is_read         = db.Column(db.Boolean, default=False)

    conversation = db.relationship('Conversation', backref=db.backref('messages', lazy='dynamic', cascade='all, delete-orphan'))
    sender       = db.relationship('User', foreign_keys=[sender_id])
    receiver     = db.relationship('User', foreign_keys=[receiver_id])

    def __repr__(self):
        return f"Message({self.id}, {self.sender_id}->{self.receiver_id})"


# ──────────────────────────────────────────────
# Event Listeners for Automatic SEO Slug Generation
# ──────────────────────────────────────────────
from sqlalchemy import event
from utils.seo import slugify

@event.listens_for(Category, 'before_insert')
@event.listens_for(Category, 'before_update')
def receive_category_slug(mapper, connection, target):
    if not target.slug or target.name != getattr(target, '_last_name', None):
        target.slug = slugify(target.name)
        target._last_name = target.name

@event.listens_for(Blog, 'before_insert')
@event.listens_for(Blog, 'before_update')
def receive_blog_slug(mapper, connection, target):
    if not target.slug or target.title != getattr(target, '_last_title', None):
        target.slug = slugify(target.title)
        target._last_title = target.title


