import subprocess
import os

from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, Unicode, UnicodeText
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session

# These are default MAMP settings (except for MYSQL_PORT):
MYSQL_PATH = '/Applications/MAMP/Library/bin/'
ROOT_USER = 'root'
ROOT_PASSWORD = 'root'
MYSQL_PORT = 3306

# This hash corresponds to password 'admin'.
# Generated by
# http://scriptserver.mainframe8.com/wordpress_password_hasher.php
ADMIN_ADMIN_HASH = '$P$B/ej8NzIfaHWy10tQm6.lQvO0R2LFq.'

Base = declarative_base()


class Option(Base):
    __tablename__ = 'wp_options'
    option_id = Column(Integer, primary_key=True)
    option_name = Column(String)
    option_value = Column(String)


class User(Base):
    __tablename__ = 'wp_users'
    ID = Column(Integer, primary_key=True)
    user_login = Column(String)
    user_pass = Column(String)


class Term(Base):
    __tablename__ = 'wp_terms'
    term_id = Column(Integer, primary_key=True)
    name = Column(String)
    slug = Column(String)
    children = relationship('TermTaxonomy')


class TermTaxonomy(Base):
    __tablename__ = 'wp_term_taxonomy'
    term_taxonomy_id = Column(Integer, primary_key=True)
    term_id = Column(Integer, ForeignKey('wp_terms.term_id'))
    taxonomy = Column(String)
    parent = Column(Integer)


class WordpressDB(object):
    def __init__(self, user, password, database):
        self.data = {
            'root_user': ROOT_USER,
            'root_password': ROOT_PASSWORD,
            'user': user,
            'password': password,
            'database': database,
            'host': 'localhost',
            'port': MYSQL_PORT,
        }
        self.engine = create_engine(
            'mysql+mysqlconnector://'
            '{root_user}:{root_password}@{host}:{port}/{database}'.format(**self.data))

        session_factory = sessionmaker(bind=self.engine)
        Session = scoped_session(session_factory)
        self.session = Session()
        self.env = os.environ.copy()
        self.env['PATH'] += os.pathsep + MYSQL_PATH

    def restore_from_dump(self, filename):
        filename = os.path.abspath(filename)
        cmd = 'mysql -u {root_user} -p{root_password} < {filename}'.format(filename=filename,
                                                                           **self.data)
        subprocess.check_call([cmd], env=self.env, shell=True)

    def fix_user(self):
        sql = ("GRANT ALL PRIVILEGES ON {database}.* "
               "To '{user}'@'{host}' IDENTIFIED BY '{password}';".format(**self.data))
        cmd = ('mysql -u {root_user} -p{root_password} '
               '-e "{sql}"'.format(sql=sql, **self.data))
        subprocess.check_call([cmd], env=self.env, shell=True)

    def fix_url(self, url):
        for name in ('siteurl', 'home'):
            obj = self.session.query(Option).filter_by(option_name=name).one()
            obj.option_value = url
        self.session.commit()

    def set_admin_admin_password(self):
        admin = self.session.query(User).filter_by(user_login='admin').one()
        admin.user_pass = ADMIN_ADMIN_HASH
        self.session.commit()

    def get_all_tags(self):
        print('Getting all tags...')
        q = self.session.query(Term)
        q = q.join(TermTaxonomy)
        q = q.filter(TermTaxonomy.taxonomy == 'post_tag')
        return q.all()

    def get_all_categories(self):
        categories = (self.session.query(Term).
            join(TermTaxonomy).filter(TermTaxonomy.taxonomy == 'category').all())
        ids = self.session.query(TermTaxonomy).filter_by(taxonomy='category').all()
        for c in categories:
            c.parent = None
            parent = self.session.query(TermTaxonomy).filter_by(term_id=c.term_id).one().parent
            c.parent = parent if parent != 0 else None
            name = 'category_{}_acf_cat_content'.format(c.term_id)
            content = self.session.query(Option).filter_by(option_name=name).first()
            c.content = None if content is None else content.option_value
        return categories
