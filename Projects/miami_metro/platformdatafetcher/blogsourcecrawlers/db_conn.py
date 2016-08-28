# -*- coding: utf-8 -*-

try:
    from peewee import *
except ImportError:
    raise ImportError("Peewee lib is required (pip install peewee)")

DB = SqliteDatabase('lookbook.db')

class BaseModel(Model):
    class Meta:
        database = DB

class User(BaseModel):
    id = PrimaryKeyField()
    name = CharField()
    info = CharField()
    fans = CharField()
    lookbook_url = CharField()
    website_url = CharField()
    blog_url = CharField()

DB.connect()

if not User.table_exists():
    User.create_table()
