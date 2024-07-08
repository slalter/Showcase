from sqlalchemy import text, create_engine
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
import time

def reset_db(app, db):
    
    with app.app_context():
        db.drop_all()
        db.create_all()

    print("Database initialized")
    #set alembic version to head
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.stamp(alembic_cfg, "head")
    print("Alembic version set to head")

def createDefaultObjects(app, db):
    from models import  Product
    with app.app_context():
        create_default_users(app, db)
        createDefaultProducts(app, db)

def create_default_users(app, db):
    #create two default users with admin privileges: '' and tim@a3e.com
    from models import User
    user = User.find_by_email('',db)
    if not user:
        user = User(
            email = 'REDACTED',
            is_verified = True,
            is_admin = True,
            first_name = '',
            last_name = ''
        )
        db.session.add(user)
        db.session.commit()
    user = User.find_by_email('',db)
    if not user:
        user = User(
            email = '',
            is_verified = True,
            is_admin = True,
            first_name = '',
            last_name = ''
        )
        db.session.add(user)
        db.session.commit()
    print("Default users created")




def createDefaultProducts(app,db):
    defaults = []
    from models import Product
    #delete all current product objects
    db.session.query(Product).delete()
    for product in defaults['products']:
        producttype = product['producttype']
        subfolders = product['subfolders']
        product = Product(
            name = producttype,
            folders = subfolders
        )
        db.session.add(product)
        db.session.commit()
    print("Default products created")


