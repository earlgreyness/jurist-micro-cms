# -*- coding: utf-8 -*-

import json

from bs4 import BeautifulSoup
from sqlalchemy.sql.expression import case
from sqlalchemy import text

import models

HTTP_TIMESTAMP = 'ddd, DD MMM YYYY HH:mm:ss'


def dict_to_json(data):
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)


def to_http_timestamp(arrow_datetime):
    return arrow_datetime.to('utc').format(HTTP_TIMESTAMP) + ' GMT'


def _postprocess_html(html):
    return (
        html.replace('"http://{}/'.format(models.app.config['DOMAIN_NAME']), '"/')
    )


def fix_all_pages():
    db = models.db
    Page = models.Page
    Question = models.Question
    try:
        pages = db.session.query(Page).all()
        for page in pages:
            page.content = _postprocess_html(page.content)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    try:
        questions = db.session.query(Question).all()
        for question in questions:
            question.content_question = _postprocess_html(question.content_question)
            question.content_answer = _postprocess_html(question.content_answer)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def init_db():
    db = models.db
    try:
        db.metadata.drop_all(bind=db.engine)
        db.metadata.create_all(bind=db.engine)

        types = [
            'main',
            'static',
            'category',
            'subcategory',
            'service',
            'paper',
        ]
        for t in types:
            db.session.add(models.PageKind(kind=t))

        db.session.flush()

        values = [
            ('static', 'main'),
            ('category', 'main'),
            ('subcategory', 'category'),
            ('paper', 'category'),
            ('paper', 'subcategory'),
            ('service', 'category'),
            ('service', 'subcategory'),
        ]
        for c, p in values:
            db.session.add(models.PossibleRelation(
                child_kind=c,
                parent_kind=p,
            ))

        db.session.add(models.User(
            login='admin',
            name='Administrator',
            password=models.app.config['DEFAULT_ADMIN_PASSWORD'],
            role='admin',
            email='admin@{domain}'.format(domain=models.app.config['DOMAIN_NAME']),
        ))

        db.session.add(models.Jurist(
            name=u'Борисов Олег Викторович',
            job_title=u'Юрист-консультант',
            face='face_1.png',
        ))

        db.session.commit()
        print('Commited')

    except Exception:
        db.session.rollback()
        raise
