# -*- coding: utf-8 -*-

import json
import logging
import logging.handlers
import functools
from collections import namedtuple
import datetime

import dateutil.parser
import arrow
from jinja2 import TemplateNotFound
import requests
from werkzeug.routing import BaseConverter
from flask import (Flask, request, redirect, url_for, render_template,
                   abort, make_response, send_from_directory, session, g)
from flask_sqlalchemy import SQLAlchemy, Pagination
from flask_restful import Api, Resource
from flask_login import (LoginManager, login_user,
                         logout_user, current_user, login_required)
from sqlalchemy.orm.exc import NoResultFound
import sqlalchemy.exc
import sqlalchemy
from flask_caching import Cache

CACHE_SECONDS = int(datetime.timedelta(days=30).total_seconds())
QUESTIONS_PER_PAGE = 10

REDIRECTS = {
    ('msk', 'urist', 'semejnyj_jurist'):   ('family', None),
    ('msk', 'alimenty', None):             ('family', 'alimony'),
    ('msk', 'nasledstvo', None):           ('legacy', None),
    ('msk', 'urist', 'trudovoj_jurist'):   ('labor', None),
    ('msk', 'urist', 'grazhdanskie_dela'): ('civil', None),
    ('msk', 'uk', None):                   ('criminal', None),
    ('msk', 'advokat', 'voennyj_advokat'): ('military', None),
    ('msk', 'zpp', None):                  ('zpp', None),
    ('msk', 'advokat', None):              ('lawyer', None),
}

TRIPLE_REDIRECTS = {
    ('military', None, None): ('lawyer', 'military', None),
    ('civil', None, None):    ('lawyer', 'civil', None),
    ('civil', 'debt', None):  ('lawyer', 'civil', 'debt'),
}

_LABELS = [
    'thanks',
    'document',
    'answer',
    'reports',
    'question-answer',
    'visit',
    'paid-legal-advice',
    'contacts',
]
TEMPLATES_MAPPING = {label: 'company/{}.html'.format(label) for label in _LABELS}

MenuItem = namedtuple('MenuItem', 'name, url, important')


class LabelConverter(BaseConverter):
    def __init__(self, url_map):
        super(LabelConverter, self).__init__(url_map)
        self.regex = r'[a-z0-9-]{1,}'
        # self.weight = 1


class ShortcodesProxy(object):
    @staticmethod
    def get(code, default=None):
        try:
            return (db.session.query(models.Shortcode.value)
                              .filter_by(key=code).scalar() or default)
        except Exception as e:
            app.logger.error('Error in ShortcodesProxy: {}'.format(e))
        return default


class CustomFlask(Flask):
    jinja_options = Flask.jinja_options.copy()
    jinja_options['trim_blocks'] = True
    jinja_options['lstrip_blocks'] = True


# static_url_path must be long and
# must correspond to apache static path.
app = CustomFlask(__name__, static_folder='static',
                  static_url_path='/static/content/themes/user')
app.config.from_object('config')

try:
    handler = logging.handlers.RotatingFileHandler(
        'logs/app.log',
        encoding='utf-8',
        maxBytes=102400,
        backupCount=10,
    )
except OSError:
    handler = logging.NullHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.WARNING)

app.url_map.converters['label'] = LabelConverter

db = SQLAlchemy(app)
api = Api(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'strong'

# cache = RedisCache(port=6379, default_timeout=0, key_prefix=None)
# cache = Cache(app, config={
#     'CACHE_TYPE': 'redis',
#     'CACHE_DEFAULT_TIMEOUT': 0,
#     'CACHE_REDIS_PORT': 6379,
# })


@app.template_filter('replace_shortcodes')
def do_replace_shortcodes(value):
    try:
        shortcodes = db.session.query(models.Shortcode).all()
    except Exception as e:
        app.logger.error(e)
        shortcodes = []
    for shortcode in shortcodes:
        value = value.replace('[{}]'.format(shortcode.key), shortcode.value)
    return value


@login_manager.user_loader
def load_user_from_db(login):
    try:
        return db.session.query(models.User).filter_by(login=login).one()
    except Exception:
        app.logger.exception('Error when loading user.')
    return None


@app.before_request
def run_before_each_request():
    g.shortcodes = ShortcodesProxy()
    g.now = arrow.now()


@app.errorhandler(404)
def page_not_found(e):
    try:
        page = models.Page(kind='static', heading=u'Страница не найдена')
        response = make_response(render_template('company/404.html', page=page), 404)
    except Exception:
        app.logger.exception('Error rendering 404 page.')
        response = make_response('Page not found', 404)
    response.headers['Cache-Control'] = 'no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@app.errorhandler(500)
def server_error_handler(e):
    app.logger.exception('Internal Server Error')
    return '<h1>500 Internal Server Error</h1>', 500


@app.route('/')
def render_index():
    return render_category(category='main', disallow_main=False)


@app.route('/thanks/')
def thanks():
    page = models.Page(kind='static', heading=u'Спасибо за обращение!')
    return _generate_response('company/thanks.html', page=page)


@app.route('/msk/<topic>/')
@app.route('/msk/<topic>/<phrase>')
def render_cascade(topic, phrase=None):
    parts = ('msk', topic, phrase)
    if parts not in REDIRECTS:
        abort(404)
    data = dict(zip(('category', 'subcategory'), REDIRECTS[parts]))
    return redirect(url_for('render_category', **data), code=301)


@app.route('/robots.txt')
def render_robots():
    return send_from_directory(app.static_folder, 'robots.txt')


@app.route('/favicon.ico')
def render_favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')


@app.route('/sitemap.xml')
def render_sitemap():
    Page = models.Page
    Question = models.Question
    pages = (db.session.query(Page)
                       .order_by(Page.kind.desc(), Page.priority, Page.id).all())
    questions = db.session.query(Question).order_by(Question.id).all()
    response = make_response(render_template('company/sitemap.xml',
                                             pages=pages,
                                             questions=questions))
    response.headers['Content-Type'] = 'text/xml; charset=utf-8'
    response.headers['X-Robots-Tag'] = 'noindex'
    response.headers['Cache-Control'] = 'max-age={}'.format(CACHE_SECONDS)
    return response


def generate_navigation_menu(page):
    Page = models.Page

    def get_item(p):
        if p.label == page.label or p.should_be_404():
            url = None
        else:
            url = p.get_url()
        important = p.kind in ['category', 'subcategory']
        return MenuItem(name=p.heading, url=url, important=important)

    shown = ['category', 'subcategory', 'service']
    if not (page.is_main() or page.kind in shown):
        return []
    if page.kind == 'service':
        parent_id = page.parent_id
    else:
        parent_id = page.id
    cases = sqlalchemy.case([(Page.kind == k, n) for n, k in enumerate(shown)])
    pages = (
        db.session.query(Page)
                  .filter_by(parent_id=parent_id)
                  .filter_by(visible_in_menu=True)
                  .filter(Page.kind.in_(shown))
                  .order_by(cases, Page.priority, Page.id).all()
    )
    return [get_item(p) for p in pages]


def get_page_cascade(*parts):

    def get_page(label):
        if label is None:
            return None
        return models.Page.get_by_label(label)

    def check(parts, masks):
        return all((a is not None) is bool(b) for a, b in zip(parts, masks))

    try:
        pages = tuple(get_page(label) for label in parts)
    except NoResultFound:
        return None

    try:
        if check(parts, (1, 0, 0)):
            assert pages[0].kind in ['main', 'static', 'category']
            return pages[0]

        if check(parts, (1, 1, 0)):
            assert pages[0].kind == 'category'
            assert pages[0].is_parent_of(pages[1])
            return pages[1]

        if check(parts, (1, 1, 1)):
            assert pages[0].kind == 'category'
            assert pages[1].kind == 'subcategory'
            assert pages[0].is_parent_of(pages[1])
            assert pages[1].is_parent_of(pages[2])
            return pages[2]
    except AssertionError:
        pass
    return None


def render_question_answer():
    Question = models.Question
    try:
        number = int(request.args.get('page') or 1)
    except ValueError:
        number = 1

    if number < 1:
        abort(404)

    try:
        page = models.Page.get_by_label('question-answer')
    except NoResultFound:
        abort(404)

    total = db.session.query(Question.id).count()
    questions = (
        db.session.query(Question)
                  .order_by(Question.id.desc())
                  .limit(QUESTIONS_PER_PAGE)
                  .offset(QUESTIONS_PER_PAGE * (number - 1)).all()
    )
    if not questions and number != 1:
        abort(404)
    pagination = Pagination(None, number, QUESTIONS_PER_PAGE, total, items=questions)
    modified = (
        db.session.query(Question.date_modified)
                  .order_by(Question.date_modified.desc()).limit(1).scalar()
    )
    if modified and modified > page.date_modified:
        page.date_modified = modified
    return _generate_response('company/question-answer.html', page=page,
                              pagination=pagination)


@app.route('/question-answer/<int:id>/')
def render_single_question(id):
    question = db.session.query(models.Question).get(id)
    if question is None:
        abort(404)
    return _generate_response('company/single-question.html',
                              page=question.generate_page(),
                              question=question)


def _generate_response(template, **kwargs):
    try:
        stamp = request.headers['If-Modified-Since']
        if_modified_since = arrow.get(dateutil.parser.parse(stamp))
        last_modified = kwargs['page'].date_modified
        if last_modified and last_modified < if_modified_since:
            return make_response('', 304)
    except KeyError:
        pass
    except Exception:
        app.logger.exception('Could not handle If-Modified-Since.')
        pass

    try:
        response = make_response(render_template(template, **kwargs))
    except TemplateNotFound:
        app.logger.exception('Template not found.')
        abort(404)
    try:
        response.headers['Last-Modified'] = \
            utils.to_http_timestamp(kwargs['page'].date_modified)
    except (KeyError, AttributeError):
        # AttributeError is raised if page.date_modified is None
        pass
    response.headers['Cache-Control'] = 'max-age={}'.format(CACHE_SECONDS)
    return response


@app.route('/<label:category>/')
@app.route('/<label:category>/<label:subcategory>/')
@app.route('/<label:category>/<label:subcategory>/<label:article>/')
def render_category(category, subcategory=None, article=None, disallow_main=True):
    parts = (category, subcategory, article)

    def _redirect(*triple):
        packed = dict(zip(['category', 'subcategory', 'article'], triple))
        return redirect(('render_category', **packed), code=301)

    if parts in TRIPLE_REDIRECTS:
        return _redirect(*TRIPLE_REDIRECTS[parts])
    if parts == ('question-answer', None, None):
        return render_question_answer()

    page = get_page_cascade(*parts)
    if (page is None or
            page.is_main() and disallow_main or
            page.should_be_404()):
        abort(404)
    menu = generate_navigation_menu(page)
    template = TEMPLATES_MAPPING.get(page.label, 'company/page.html')
    return _generate_response(template, page=page, menu=menu)


@app.route('/sender', methods=['POST'])
def send_lead_to_crm():
    try:
        lead = {}
        f = request.form
        lead['domain'] = 'jurist-msk'
        lead['source'] = f.get('source_url') or request.url
        lead['phone'] = f.get('phone', '')
        lead['name'] = f.get('name', '')
        lead['question'] = ''
        if f.get('purpose') == 'callback':
            lead['question'] += u'Обратный звонок\n'
        if 'doctype' in f:
            lead['question'] = (
                u'Заказ документа: {} ({})\n'.format(f.get('doctype'),
                                                     f.get('doctype_detailed'))
            )
        if 'category' in f:
            lead['question'] = u'Категория права: {}\n'.format(f.get('category'))
        if f.get('question'):
            lead['question'] = u'{} Комментарий: {}'.format(lead['question'],
                                                            f.get('question'))
        requests.post(app.config['CRM_URL'], json=lead)
        app.logger.info('LEAD SENT TO CRM: {}'.format(dict_to_json(lead)))
    except Exception:
        app.logger.exception('Lead not processed in /sender')

    try:
        lead_ = leads_distributor.Lead(request.form)
        if not lead_.is_spam():
            leads_distributor.send_to_roistat(lead_)
    except Exception:
        app.logger.exception('Lead not sent to Roistat')

    return redirect(url_for('thanks'))


@app.route('/zvonok/')
def zvonok():
    return redirect(app.config['CALLCENTER_URL'], code=301)





















@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    session.permanent = False
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            user = db.session.query(models.User).filter_by(login=username).one()
        except NoResultFound:
            # No such user.
            pass
        else:
            if user.check_password(password):
                login_user(user, remember=False)
            else:
                # Invalid password.
                pass

    next_location = request.args.get('next')
    if current_user.is_authenticated:
        return redirect(next_location or url_for('render_admin'))
    return render_template('admin/admin_login.html')


@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/admin')
@login_required
def render_admin():
    return redirect(url_for('admin_category_list'))


@app.route('/admin/question/add')
@login_required
def admin_question_add():
    return render_template('admin/admin_alter_question.html',
                           action='create')

@app.route('/admin/question/edit/<int:id>')
@login_required
def admin_question_edit(id):
    return render_template('admin/admin_alter_question.html',
                           action='update',
                           object_id=id)

@app.route('/admin/question/list')
@login_required
def admin_question_list():
    Question = models.Question
    questions = (db.session.query(Question)
                           .order_by(Question.id).all())
    return render_template('admin/admin_list_question.html', questions=questions)


@app.route('/admin/service/add')
@login_required
def admin_service_add():
    return render_template('admin/admin_alter_page.html',
                           purpose='service',
                           action='create')

@app.route('/admin/service/edit/<int:id>')
@login_required
def admin_service_edit(id):
    return render_template('admin/admin_alter_page.html',
                           purpose='service',
                           action='update',
                           object_id=id)

@app.route('/admin/service/list')
@login_required
def admin_service_list():
    pages = models.Page.get_sorted_pages('service')
    return render_template('admin/admin_list_service.html', pages=pages)


@app.route('/admin/paper/add')
@login_required
def admin_paper_add():
    return render_template('admin/admin_alter_page.html',
                           purpose='paper',
                           action='create')

@app.route('/admin/paper/edit/<int:id>')
@login_required
def admin_paper_edit(id):
    return render_template('admin/admin_alter_page.html',
                           purpose='paper',
                           action='update',
                           object_id=id)

@app.route('/admin/paper/list')
@login_required
def admin_paper_list():
    pages = models.Page.get_sorted_pages('paper')
    return render_template('admin/admin_list_paper.html', pages=pages)


@app.route('/admin/category/add')
@login_required
def admin_category_add():
    return render_template('admin/admin_alter_page.html',
                           purpose='category',
                           action='create')

@app.route('/admin/category/edit/<int:id>')
@login_required
def admin_category_edit(id):
    return render_template('admin/admin_alter_page.html',
                           purpose='category',
                           action='update',
                           object_id=id)

@app.route('/admin/category/list')
@login_required
def admin_category_list():
    categories = models.Category.get_all()
    rendered = render_template('admin/admin_list_category.html', categories=categories)
    return rendered


@app.route('/admin/static/list')
@login_required
def admin_static_list():
    Page = models.Page
    pages = (db.session.query(Page)
                       .filter(Page.kind.in_(['static', 'main']))
                       .order_by(Page.label).all())
    return render_template('admin/admin_list_static.html', pages=pages)


@app.route('/admin/static/add')
@login_required
def admin_static_add():
    return render_template('admin/admin_alter_page.html',
                           purpose='static',
                           action='create')


@app.route('/admin/static/edit/<int:id>')
@login_required
def admin_static_edit(id):
    return render_template('admin/admin_alter_page.html',
                           purpose='static',
                           action='update',
                           object_id=id)


@app.route('/admin/shortcode/list')
@login_required
def admin_shortcode_list():
    codes = db.session.query(models.Shortcode).order_by(models.Shortcode.key).all()
    return render_template('admin/admin_list_shortcode.html', shortcodes=codes)


@app.route('/admin/shortcode/add')
@login_required
def admin_shortcode_add():
    return render_template('admin/admin_alter_shortcode.html',
                           action='create')


@app.route('/admin/shortcode/edit/<int:id>')
@login_required
def admin_shortcode_edit(id):
    return render_template('admin/admin_alter_shortcode.html',
                           action='update',
                           object_id=id)






class BaseResponse(tuple):
    def __new__(cls, data=None, message='', code=200):
        j = {'Data': data, 'Message': message}
        return super(BaseResponse, cls).__new__(cls, (j, code))


class ErrorResponse(BaseResponse):
    def __new__(cls, message, code=500):
        return super(ErrorResponse, cls).__new__(cls, message=message, code=code)


class SuccessResponse(BaseResponse):
    def __new__(cls, data=None):
        return super(SuccessResponse, cls).__new__(cls, data=data, code=200)


def intercept_exceptions(f):
    @functools.wraps(f)
    def func(*args, **kwargs):
        try:
            value = f(*args, **kwargs)
            return value if isinstance(value, BaseResponse) else SuccessResponse(value)
        except Exception as e:
            if not isinstance(e, sqlalchemy.exc.IntegrityError):
                app.logger.exception('Error when using ajax API.')
            message = u'{}: {}'.format(type(e).__name__, e)
            return ErrorResponse(message)
    return func


class TagsAutocomplete(Resource):
    def get(self):
        try:
            query = request.args.get('query')
            if query is None:
                return []
            template = u'%{}%'.format(query.strip())
            Tag = models.Tag
            tags = (db.session.query(Tag).filter(Tag.name.ilike(template))
                              .order_by(Tag.name).all())
            return [{'text': tag.name} for tag in tags]
        except Exception:
            app.logger.exception('Cannot fetch tags.')
            return []


class JuristsList(Resource):
    @login_required
    @intercept_exceptions
    def get(self):
        Jurist = models.Jurist
        return [j.json() for j in db.session.query(Jurist).order_by(Jurist.id).all()]


class CategoryResource(Resource):
    @login_required
    @intercept_exceptions
    def get(self):
        only_root = request.args.get('only_root', 'false').lower() == 'true'
        return [c.json() for c in models.Category.get_all(only_root=only_root)]


class PageResource(Resource):
    """
    Working with single Page or Static Page.
    """

    @login_required
    @intercept_exceptions
    def get(self):
        id = int(request.args['id'])
        page = db.session.query(models.Page).get(id)
        if page is None:
            return ErrorResponse('Page with id={} not found'.format(id), 404)
        return page.json()

    @login_required
    @intercept_exceptions
    def post(self):
        models.Page.api_create(request.json)
        # cache.clear()

    @login_required
    @intercept_exceptions
    def put(self):
        models.Page.api_update(request.json)
        # cache.clear()

    @login_required
    @intercept_exceptions
    def delete(self):
        id = int(request.args['id'])
        models.Page.api_delete(id)
        # cache.clear()


class QuestionResource(Resource):
    @login_required
    @intercept_exceptions
    def get(self):
        id = int(request.args['id'])
        return db.session.query(models.Question).get(id).json()

    @login_required
    @intercept_exceptions
    def post(self):
        models.Question.api_create(request.json)
        # cache.clear()

    @login_required
    @intercept_exceptions
    def put(self):
        models.Question.api_update(request.json)
        # cache.clear()

    @login_required
    @intercept_exceptions
    def delete(self):
        id = int(request.args['id'])
        models.Question.api_delete(id)
        # cache.clear()


class ShortcodeResource(Resource):
    @login_required
    @intercept_exceptions
    def get(self):
        id = int(request.args['id'])
        return db.session.query(models.Shortcode).get(id).json()

    @login_required
    @intercept_exceptions
    def post(self):
        models.Shortcode.api_create(request.json)
        # cache.clear()

    @login_required
    @intercept_exceptions
    def put(self):
        models.Shortcode.api_update(request.json)
        # cache.clear()

    @login_required
    @intercept_exceptions
    def delete(self):
        id = int(request.args['id'])
        models.Shortcode.api_delete(id)
        # cache.clear()


class LabelPicker(Resource):
    @login_required
    @intercept_exceptions
    def get(self):
        name = request.args.get('name', '')
        try:
            page_id = int(request.args.get('page_id'))
        except TypeError:
            page_id = None
        return models.Page.pick_label_by_name(name, page_id=page_id)


class LabelChecker(Resource):
    @login_required
    @intercept_exceptions
    def get(self):
        label = request.args['label']
        try:
            page_id = int(request.args.get('page_id'))
        except TypeError:
            page_id = None
        return models.Page.is_label_vacant(label, page_id=page_id)


api.add_resource(TagsAutocomplete, '/admin/api/tags')
api.add_resource(JuristsList, '/admin/api/jurists')
api.add_resource(CategoryResource, '/admin/api/categories')
api.add_resource(QuestionResource, '/admin/api/question')

api.add_resource(PageResource, '/admin/api/page')

api.add_resource(LabelPicker, '/admin/api/label/pick')
api.add_resource(LabelChecker, '/admin/api/label/check')

api.add_resource(ShortcodeResource, '/admin/api/shortcode')

import models
import utils
import leads_distributor


if __name__ == '__main__':
    app.logger.setLevel(logging.DEBUG)
    app.run(debug=True)
