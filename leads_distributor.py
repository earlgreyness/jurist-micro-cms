# -*- coding: utf-8 -*-

# import urllib.parse

import requests
import flask
import phonenumbers
from phonenumbers import format_number, PhoneNumberFormat, NumberParseException

import flaskapp

COUNTRY = 'RU'


class Lead(object):
    def __init__(self, data):
        self.name = data.get('name', '')
        self.phone = self.parse_phone(data.get('phone', ''))
        self.question = data.get('question', '')
        self.source = data.get('source_url') or flask.request.url
        self.topic = data.get('topic')

    @staticmethod
    def parse_phone(number):
        digits = ''.join(d for d in str(number) if d.isdigit())
        try:
            phone = phonenumbers.parse(digits, COUNTRY)
        except NumberParseException:
            return digits
        else:
            formatted = format_number(phone, PhoneNumberFormat.E164)
            return formatted[1:]  # Removing leading '+' symbol

    def is_spam(self):
        base_length = len('4950001122')
        return len(self.phone) < base_length

    def format_for_leadok(self):
        return {
            'name': self.name,
            'phone': self.phone,
            'question': self.question,
            'domain': 'jurist-msk',
            'source': self.source,
        }

    def build_amocrm_title(self):
        FALLBACK_TOPIC = u''
        topic = self.topic or FALLBACK_TOPIC
        template = u'Заявка для {specialist}. {topic}'
        data = {}
        data['topic'] = topic
        if 'lawyer' in self.source:
            data['specialist'] = u'Адвоката'
        else:
            data['specialist'] = u'Юриста'
        return template.format(**data)

    def format_for_roistat(self):
        FLD_QUESTION = '1565056'
        FLD_CITY = '1574354'
        return {
            'roistat': flask.request.cookies.get('roistat_visit'),
            'key': flaskapp.app.config['ROISTAT_KEY'],
            'title': self.build_amocrm_title(),
            'comment': self.question,
            'name': self.name,
            'email': '',
            'phone': self.phone,
            'is_need_check_order': '1',
            'fields': {
                FLD_QUESTION: self.question,
                FLD_CITY: r'{city}',
                'is_need_check_order': '1',
            },
        }


def _flatten(data, name):
    if name not in data:
        return data
    fixed = data.copy()
    upd = {'{}[{}]'.format(name, k): v for k, v in fixed[name].items()}
    fixed.update(upd)
    del fixed[name]
    return fixed


def send_to_roistat(lead):
    data = _flatten(lead.format_for_roistat(), 'fields')
    # r = requests.Request('GET', flaskapp.app.config['ROISTAT_URL'], params=data)
    # prepared = r.prepare()
    # requests.Session().send(prepared)
    requests.get(flaskapp.app.config['ROISTAT_URL'], params=data)


def send_to_leadok(lead):
    requests.post(flaskapp.app.config['CRM_URL'], json=lead.format_for_leadok())
