from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created  = db.Column(db.DateTime, default=datetime.utcnow)
    cart     = db.relationship('CartItem', backref='user', lazy=True)

class Product(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    price       = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    category    = db.Column(db.String(50))
    stock       = db.Column(db.Integer, default=0)
    image       = db.Column(db.String(300), default='')
    is_best     = db.Column(db.Boolean, default=False)
    is_new      = db.Column(db.Boolean, default=False)
    is_active   = db.Column(db.Boolean, default=True)
    created     = db.Column(db.DateTime, default=datetime.utcnow)
    cart_items  = db.relationship('CartItem', backref='product', lazy=True)

class CartItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    quantity   = db.Column(db.Integer, default=1)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
