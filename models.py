# -*- coding: utf-8 -*-

import hashlib
import functools
import re
from enum import Enum
from collections import namedtuple
import random

import arrow
from bs4 import BeautifulSoup
import transliterate
import jinja2.filters
import sqlalchemy
from sqlalchemy import (
    Table, Column as BaseColumn, CheckConstraint,
    UniqueConstraint, Index, ForeignKeyConstraint, ForeignKey,
    Boolean, String, UnicodeText, Integer, PrimaryKeyConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy_utils import ArrowType
import flask

from flaskapp import db, app
import utils


LABEL_REGEX = r'^[a-z0-9-]{1,}$'
KIND_REGEX = r'^[a-z]{1,}$'
LABEL_REGEX_COMPILED = re.compile(LABEL_REGEX)
LONG_DASH_PREFIX = u'— '
SALT = 'salt_sef3r3++---03'
HTML_PARSER = 'html.parser'
LANG = 'ru'

Action = Enum('Action', 'CREATE, MODIFY')
Breadcrumb = namedtuple('Breadcrumb', 'name, url')
Column = functools.partial(BaseColumn, nullable=False)
CascadeForeignKey = functools.partial(ForeignKey, ondelete='CASCADE')


class ApiMixin(object):
    @classmethod
    def api_delete(cls, id, commit=True):
        try:
            obj = db.session.query(cls).get(id)
            assert obj is not None
            db.session.delete(obj)
            if commit:
                db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def api_create(cls, data, commit=True):
        cls.api_alter(data, action=Action.CREATE, commit=commit)

    @classmethod
    def api_update(cls, data, commit=True):
        cls.api_alter(data, action=Action.MODIFY, commit=commit)

    @classmethod
    def api_alter(cls, data, action=Action.CREATE, commit=True):
        data = cls.api_fix_data(data)
        try:
            if action is Action.CREATE:
                obj = cls()
            elif action is Action.MODIFY:
                obj = db.session.query(cls).filter_by(id=data['id']).one()

            cls._api_alter(obj, data)

            if action is Action.CREATE:
                db.session.add(obj)
            if commit:
                db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def api_fix_data(data):
        fixed = data.copy()
        keys_id = ['id', 'parent_id', 'jurist_id']
        keys_html = ['content', 'content_question', 'content_answer']
        keys_else = [
            'heading', 'title', 'content', 'description', 'kind',
            'aux_field_1', 'aux_field_2', 'aux_field_3',
            'content_question', 'content_answer',
            'key', 'value', 'comment', 'author',
        ]
        for key in keys_id:
            try:
                fixed[key] = int(data.get(key))
            except TypeError:
                fixed[key] = None

        for key in keys_else:
            fixed[key] = data.get(key, '').strip()
            if key in keys_html:
                try:
                    fixed[key] = utils._postprocess_html(fixed[key])
                except Exception:
                    app.logger.exception('Error parsing html content.')

        fixed['label'] = data.get('label', '').lower().strip()
        fixed['priority'] = int(data.get('priority', 0))
        fixed['visible_in_menu'] = bool(data.get('visible_in_menu', True))
        fixed['tags'] = [tag['text'].strip() for tag in data.get('tags', [])]
        return fixed


class TagsGetterMixin(object):
    def get_tags_as_json(self):
        arr = [{'text': tag.name} for tag in self.tags]
        arr.sort(key=lambda x: x['text'])
        return arr


class CreatedModifiedMixin(object):
    date_created  = Column(ArrowType(timezone=True), default=arrow.utcnow)
    date_modified = Column(ArrowType(timezone=True), default=arrow.utcnow,
                           onupdate=arrow.utcnow)


questions_and_tags_table = Table('questions_and_tags', db.metadata,
    Column('question_id', Integer, CascadeForeignKey('questions.id')),
    Column('tag_id', Integer, CascadeForeignKey('tags.id')),
    PrimaryKeyConstraint('question_id', 'tag_id'),
)

pages_and_tags_table = Table('pages_and_tags', db.metadata,
    Column('page_id', Integer, CascadeForeignKey('pages.id')),
    Column('tag_id', Integer, CascadeForeignKey('tags.id')),
    PrimaryKeyConstraint('page_id', 'tag_id'),
)


class PageKind(db.Model):
    __tablename__ = 'kinds'
    kind = Column(String, CheckConstraint("kind ~ '{}'".format(KIND_REGEX)),
                  primary_key=True)


class PossibleRelation(db.Model):
    __tablename__ = 'possible_relations'

    child_kind  = Column(String, ForeignKey('kinds.kind'))
    parent_kind = Column(String, ForeignKey('kinds.kind'))

    __table_args__ = (
        PrimaryKeyConstraint('child_kind', 'parent_kind'),
    )


class Tag(db.Model):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText, CheckConstraint("length(name) > 1"),
                  unique=True)

    __table_args__ = (
        Index("index_unique_lowercase_tag_name",
              sqlalchemy.text("lower(name)"),
              unique=True),
    )

    def __init__(self, name):
        self.name = name

    @classmethod
    def add_by_names(cls, names):
        for name in names:
            query = db.session.query(cls.id).filter(cls.name.ilike(name))
            if not query.count():
                db.session.add(cls(name=name))

    @classmethod
    def get_by_names(cls, names):
        if not names:
            return []
        conds = [cls.name.ilike(name) for name in names]
        return (
            db.session.query(cls)
                      .filter(sqlalchemy.or_(*conds))
                      .order_by(cls.name).all()
        )

    def __repr__(self):
        return u"Tag('{}')".format(self.name)


class Page(CreatedModifiedMixin, TagsGetterMixin, ApiMixin, db.Model):
    __tablename__ = 'pages'

    id              = Column(Integer, primary_key=True)
    label           = Column(String,
                             CheckConstraint("label ~ '{}'".format(LABEL_REGEX)), unique=True)
    heading         = Column(UnicodeText,
                             CheckConstraint("length(heading) > 0"))
    title           = Column(UnicodeText, default='')
    description     = Column(UnicodeText, default='')
    content         = Column(UnicodeText, default='')
    kind            = Column(String, ForeignKey('kinds.kind'))
    priority        = Column(Integer, default=0)
    visible_in_menu = Column(Boolean, default=True)
    parent_id       = Column(Integer, nullable=True)
    parent_kind     = Column(String, nullable=True)
    aux_field_1     = Column(UnicodeText, default='')
    aux_field_2     = Column(UnicodeText, default='')
    aux_field_3     = Column(UnicodeText, default='')

    tags = relationship('Tag', secondary=pages_and_tags_table, order_by='Tag.name')
    parent = relationship('Page', foreign_keys='[Page.parent_id]', remote_side=[id])

    __table_args__ = (
        UniqueConstraint('id', 'kind'),
        ForeignKeyConstraint(
            ['parent_id', 'parent_kind'],
            ['pages.id', 'pages.kind'],
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        ForeignKeyConstraint(
            ['kind', 'parent_kind'],
            ['possible_relations.child_kind', 'possible_relations.parent_kind'],
        ),
        CheckConstraint('id <> parent_id'),
        CheckConstraint(
            """(label = 'main'  AND kind = 'main'
                                AND parent_id IS NULL
                                AND parent_kind IS NULL) OR
               (label <> 'main' AND kind <> 'main'
                                AND parent_id IS NOT NULL
                                AND parent_kind IS NOT NULL)
            """
        ),
    )

    def is_parent_of(self, other):
        return self.id == other.parent_id

    def get_parents(self):
        parents = ()
        parent = self.parent
        while parent is not None:
            parents += (parent,)
            parent = parent.parent
        return parents

    def get_chain(self):
        return (self,) + self.get_parents()

    def get_url(self, _external=False):
        _url_for = functools.partial(flask.url_for, _external=_external)

        if self.is_main():
            return _url_for('render_index')

        words = ['category', 'subcategory', 'article']
        parts = [p.label for p in self.get_chain()[:-1][::-1]]
        return _url_for('render_category', **dict(zip(words, parts)))

    def should_be_404(self):
        return self.kind in ['service'] and self.is_content_empty()

    def is_main(self):
        return self.kind == 'main'

    def is_content_empty(self, strip_tags=False):
        if strip_tags:
            soup = BeautifulSoup(self.content, 'html5lib')
            return not soup.get_text().strip()
        return not self.content.strip()

    def generate_aux_fields(self):
        keys = ['aux_field_1', 'aux_field_2', 'aux_field_3']
        fields = {key: '' for key in keys}
        for key in fields:
            parent = self
            while not fields[key] and parent is not None:
                fields[key] = getattr(parent, key)
                parent = parent.parent
        return fields

    def generate_breadcrumbs(self):
        if getattr(self, 'breadcrumbs', None) is not None:
            return self.breadcrumbs
        if self.is_main():
            return []
        crumb = Breadcrumb(self.heading, None)
        crumbs = [Breadcrumb(p.heading, p.get_url()) for p in self.get_parents()]
        return ([crumb] + crumbs)[::-1]

    def as_category(self):
        assert self.kind in ['category', 'subcategory']
        return Category(self)

    def json(self):
        return {
            'id':              self.id,
            'label':           self.label,
            'heading':         self.heading,
            'title':           self.title,
            'description':     self.description,
            'content':         self.content,
            'visible_in_menu': self.visible_in_menu,
            'parent_id':       self.parent_id if self.kind != 'category' else None,
            'kind':            self.kind,
            'tags':            self.get_tags_as_json(),
            'priority':        self.priority,
            'aux_field_1':     self.aux_field_1,
            'aux_field_2':     self.aux_field_2,
            'aux_field_3':     self.aux_field_3,
            'url':             self.get_url(),
        }

    @classmethod
    def get_main(cls):
        return db.session.query(cls).filter_by(kind='main').one()

    @classmethod
    def get_by_label(cls, label):
        return db.session.query(cls).filter_by(label=label).one()

    @classmethod
    def get_sorted_pages(cls, kind):
        assert kind in ['paper', 'service']

        def key(page):
            par1 = page.parent
            par2 = page.parent.parent
            if par2.kind == 'category':
                return (par2.priority, par2.id,
                        par1.priority, par1.id,
                        page.priority, page.id)
            return (par1.priority, par1.id,
                    0, 0,
                    page.priority, page.id)

        pages = db.session.query(cls).filter_by(kind=kind).all()
        pages.sort(key=key)
        return pages

    @classmethod
    def _api_alter(cls, obj, data):
        page = obj

        Tag.add_by_names(data['tags'])
        page.tags = Tag.get_by_names(data['tags'])

        assert len(page.tags) == len(data['tags'])

        keys = [
            'heading', 'label', 'title', 'content', 'kind',
            'visible_in_menu', 'description', 'priority',
            'aux_field_1', 'aux_field_2', 'aux_field_3',
        ]
        for key in keys:
            setattr(page, key, data[key])

        with db.session.no_autoflush:
            if page.kind == 'main':
                parent = cls(id=None, kind=None)
            elif page.kind in ['static', 'category']:
                parent = cls.get_main()
            else:
                parent = db.session.query(cls).filter_by(id=data['parent_id']).one()

            page.parent_id = parent.id
            page.parent_kind = parent.kind


    @classmethod
    def is_label_vacant(cls, label, omit_regex=False, page_id=None):
        if not omit_regex and LABEL_REGEX_COMPILED.fullmatch(label) is None:
            return False
        query = db.session.query(cls.id).filter(cls.label == label)
        if page_id is not None:
            query = query.filter(cls.id != page_id)
        return not query.count()

    @classmethod
    def pick_label_by_name(cls, name, page_id=None):
        if not name:
            return ''
        dash = '-'
        _name = name.strip().lower().replace(' ', dash)
        label = transliterate.translit(_name, LANG, reversed=True)
        candidate = ''.join(ch for ch in label
                            if ch.isalpha() or ch.isdigit() or ch == dash)

        def construct(what, n):
            return '{}-{}'.format(what, n) if n > 0 else what

        for number in range(11):
            var = construct(candidate, number)
            if cls.is_label_vacant(var, omit_regex=True, page_id=page_id):
                return var

        return construct(candidate, random.randint(23, 99))

    def __repr__(self):
        return "<Page ('{}', '{}')>".format(self.kind, self.label)


class Category(object):
    def __init__(self, page):
        self.page = page
        assert self.page.kind in ['category', 'subcategory']

    @property
    def nested_name(self):
        if self.page.kind == 'subcategory':
            return LONG_DASH_PREFIX + self.page.heading
        return self.page.heading

    def json(self):
        return {'id': self.page.id, 'name': self.nested_name}

    @classmethod
    def get_all(cls, only_root=False):
        if only_root:
            kinds = ['category']
        else:
            kinds = ['category', 'subcategory']

        def key(p):
            if p.kind == 'category':
                return (p.priority, p.id, 0, 0)
            return (p.parent.priority, p.parent.id, p.priority, p.id)

        pages = db.session.query(Page).filter(Page.kind.in_(kinds)).all()
        pages.sort(key=key)
        return [cls(page) for page in pages]

    def _count(self, what):
        if what == 'question':
            return (
                db.session.query(Question.id)
                          .filter_by(parent_id=self.page.id).count()
            )
        return (
            db.session.query(Page.id)
                      .filter_by(kind=what)
                      .filter_by(parent_id=self.page.id).count()
        )

    def count_questions(self):
        return self._count('question')

    def count_services(self):
        return self._count('service')

    def count_papers(self):
        return self._count('paper')

    def __repr__(self):
        return '<Category ({!r})>'.format(self.page)


class Question(db.Model, TagsGetterMixin, CreatedModifiedMixin, ApiMixin):
    __tablename__ = 'questions'

    id               = Column(Integer, primary_key=True)
    parent_id        = Column(Integer, CascadeForeignKey('pages.id'))
    jurist_id        = Column(Integer, ForeignKey('jurists.id'))
    heading          = Column(UnicodeText,
                              CheckConstraint("length(heading) > 2"),
                              unique=True)
    content_question = Column(UnicodeText)
    content_answer   = Column(UnicodeText)
    author           = Column(UnicodeText)

    tags = relationship('Tag', secondary=questions_and_tags_table,
                        lazy='joined', order_by='Tag.name')
    page = relationship('Page', lazy='joined')
    jurist = relationship('Jurist', lazy='joined')

    def json(self):
        return {
            'id':               self.id,
            'parent_id':        self.parent_id,
            'heading':          self.heading,
            'author':           self.author,
            'content_question': self.content_question,
            'content_answer':   self.content_answer,
            'tags':             self.get_tags_as_json(),
            'jurist_id':        self.jurist_id,
            'url':              self.get_url(),
        }

    def get_url(self, _external=False):
        return flask.url_for('render_single_question', id=self.id, _external=_external)

    def is_answer_provided(self):
        return bool(self.content_answer.strip())

    def generate_page(self):
        try:
            soup = BeautifulSoup(self.content_question or '', HTML_PARSER)
            description = jinja2.filters.do_truncate(
                soup.get_text().strip(), length=170, killwords=False)
        except Exception:
            app.logger.exception('Error building description for a question.')
            description = ''
        page = Page(kind='static',
                    heading=self.heading,
                    title=self.heading,
                    description=description,
                    date_modified=self.date_modified)
        main = Page.get_main()
        seco = Page.get_by_label('question-answer')
        page.breadcrumbs = [
            Breadcrumb(main.heading, main.get_url()),
            Breadcrumb(seco.heading, seco.get_url()),
            Breadcrumb(page.heading, None),
        ]
        return page

    @classmethod
    def _api_alter(cls, obj, data):
        Tag.add_by_names(data['tags'])
        obj.tags = Tag.get_by_names(data['tags'])
        assert len(obj.tags) == len(data['tags'])

        keys = ['heading', 'content_question', 'parent_id',
                'content_answer', 'author', 'jurist_id']
        for key in keys:
            setattr(obj, key, data[key])

    def __repr__(self):
        return '<Question {}>'.format(self.id)


class Jurist(db.Model):
    __tablename__ = 'jurists'

    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText, CheckConstraint("length(name) > 2"))
    job_title = Column(UnicodeText)
    face = Column(String)

    def json(self):
        return {'id': self.id, 'name': self.name}

    def __repr__(self):
        return u"<Jurist ({}, '{}')>".format(self.id, self.name)


class Shortcode(db.Model, ApiMixin):
    __tablename__ = 'shortcodes'

    id = Column(Integer, primary_key=True)
    key = Column(UnicodeText, CheckConstraint("key ~ '{}'".format(LABEL_REGEX)), unique=True)
    value = Column(UnicodeText)
    comment = Column(UnicodeText)

    def json(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'comment': self.comment,
        }

    @classmethod
    def _api_alter(cls, obj, data):
        for key in ['key', 'value', 'comment']:
            setattr(obj, key, data[key])


class User(db.Model):
    __tablename__ = 'users'

    id                    = Column(Integer, primary_key=True)
    login                 = Column(String, CheckConstraint("length(login) > 2"), unique=True)
    password_hash         = Column(String)
    name                  = Column(UnicodeText)
    date_registered       = Column(ArrowType(timezone=True), default=arrow.utcnow)
    date_changed_password = Column(ArrowType(timezone=True), default=arrow.utcnow)
    email                 = Column(String)
    role                  = Column(String)

    def __init__(self, login='', name='', password='', role='admin', email=''):
        self.login = login
        self.name = name
        self.password_hash = self.get_hash(password)
        self.role = role
        self.email = email

    def __repr__(self):
        return u"<User ('{}', role='{}')>".format(self.login, self.role)

    def change_password(self, password):
        self.password_hash = self.get_hash(password)
        self.date_changed_password = arrow.now()

    def check_password(self, password):
        return self.password_hash == self.get_hash(password)

    def get_id(self):
        return self.login

    is_active = True
    is_authenticated = True
    is_anonymous = False

    @staticmethod
    def get_hash(password):
        h = hashlib.md5()
        h.update(SALT.encode('utf-8'))
        h.update(password.encode('utf-8'))
        return h.hexdigest()
