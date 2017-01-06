# -*- coding: utf-8 -*-

import subprocess
import os.path
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils

import flaskapp

config = flaskapp.app.config

LOCAL_PATH = '/Applications/Postgres.app/Contents/Versions/9.5/bin'

SETTINGS_LOCAL = dict(
   dbname='jurist-rus-database',
   username='jurist-rus',
   locale='ru_RU.UTF-8',
   psql=os.path.join(LOCAL_PATH, 'psql'),
   pg_dump=os.path.join(LOCAL_PATH, 'pg_dump'),
   createdb=os.path.join(LOCAL_PATH, 'createdb'),
)

SETTINGS_DEV = dict(
   dbname='jurist-rus-database',
   username='jurist-rus',
   locale='ru_RU.UTF-8',
   psql='psql',
   pg_dump='pg_dump',
   createdb='createdb',
)

SETTINGS = SETTINGS_DEV


def create_db():
    command = ('{createdb} {dbname} '
               '--echo '
               '--owner={username} '
               '--encoding=UTF8 '
               '--template=template0 '
               '--locale={locale} ').format(**SETTINGS)
    subprocess.check_call(command, shell=True)


def restore(infile, single_transaction=True):
    # --set ON_ERROR_STOP=on
    command = '{psql} {dbname} < {infile} '.format(infile=infile, **SETTINGS)
    if single_transaction:
        command += '--single-transaction '
    subprocess.check_call(command, shell=True)


def backup(outfile):
    # Only in PostgreSQL 9.6: '--if-exists'
    command = ('{pg_dump} {dbname} '
               '--file={outfile} '
               '--encoding=UTF8 '
               '--clean '
               '--column-inserts ').format(outfile=outfile, **SETTINGS)
    subprocess.check_call(command, shell=True)


def send_backup(send_to, dump_file):
    if not isinstance(send_to, (list, tuple)):
        send_to = [send_to]
    send_from = config['DB_BACKUP_SEND_FROM']
    subject = 'Database Backup ({dbname})'.format(**SETTINGS)
    text = 'Full backup of database "{dbname}" attached.'.format(**SETTINGS)

    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = email.utils.COMMASPACE.join(send_to)
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(text))

    with open(dump_file, 'rb') as dump:
        name = os.path.basename(dump_file)
        part = MIMEApplication(dump.read(), Name=name)
        part['Content-Disposition'] = 'attachment; filename="{}"'.format(name)
        msg.attach(part)

    try:
        smtp = smtplib.SMTP_SSL(config['DB_BACKUP_SMTP_HOST'],
                                config['DB_BACKUP_SMTP_PORT'], timeout=10)
        smtp.login(config['DB_BACKUP_LOGIN'], config['DB_BACKUP_SMTP_PASSWORD'])
        smtp.sendmail(SEND_FROM, send_to, msg.as_string())
    finally:
        smtp.close()


if __name__ == '__main__':
    # This script should be launched from postgres user.
    dump_file = '/var/lib/postgresql/dump.sql'
    backup(dump_file)
    send_backup(config['DB_BACKUP_SEND_TO'], dump_file)
