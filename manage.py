# -*- coding: utf-8 -*-

from contextlib import closing
from io import open
from logging import basicConfig, WARN
from pprint import pprint
from sys import argv

from backports import csv
from psycopg2.extensions import register_type, UNICODE, UNICODEARRAY
from pyres import ResQ
from pyres.horde import Khan
from requests import request
from simplejson import dumps
from tqdm import tqdm

from settings import PROXIES, PYRES
from utilities import (
    get_connection,
    get_details,
    get_sentry,
    get_total,
)

basicConfig(level=WARN)

register_type(UNICODE)
register_type(UNICODEARRAY)


class Record():

    queue = 'records'

    @staticmethod
    def perform(id):
        try:
            with closing(get_connection()) as connection:
                with closing(connection.cursor()) as cursor:
                    query = 'SELECT * FROM records WHERE id = %(id)s'
                    cursor.execute(
                        query,
                        {
                            'id': id,
                        },
                    )
                    record = cursor.fetchone()
                    if record['details']:
                        return
                    details = get_details(
                        record['road'],
                        record['number'],
                        record['zip_code'],
                        record['city'],
                    )
                    if not details:
                        return
                    details = dumps(
                        details,
                        ensure_ascii=False,
                        indent='    ',
                        sort_keys=True,
                    )
                    query = '''
                    UPDATE records
                    SET details = %(details)s
                    WHERE id = %(id)s
                    '''
                    cursor.execute(
                        query,
                        {
                            'details': details,
                            'id': id,
                        },
                    )
                    connection.commit()
        except Exception:
            sentry = get_sentry()
            if sentry:
                sentry.captureException()


def bootstrap():
    with closing(get_connection()) as connection:
        with closing(connection.cursor()) as cursor:
            query = 'DROP SCHEMA IF EXISTS public CASCADE'
            cursor.execute(query)

            query = 'CREATE SCHEMA IF NOT EXISTS public'
            cursor.execute(query)

            connection.commit()

        with closing(connection.cursor()) as cursor:
            query = '''
            CREATE TABLE IF NOT EXISTS records
                (
                    id INTEGER NOT NULL,
                    road CHARACTER VARYING(255) NOT NULL,
                    number CHARACTER VARYING(255) NOT NULL,
                    zip_code CHARACTER VARYING(255) NOT NULL,
                    city CHARACTER VARYING(255) NOT NULL,
                    details json NULL
                )
            '''
            cursor.execute(query)

            query = '''
            CREATE SEQUENCE records_id_sequence
                START WITH 1
                INCREMENT BY 1
                NO MINVALUE
                NO MAXVALUE
                CACHE 1
            '''
            cursor.execute(query)

            query = '''
            ALTER TABLE records
                ALTER COLUMN id
                SET DEFAULT nextval(\'records_id_sequence\'::regclass)
            '''
            cursor.execute(query)

            query = '''
            ALTER TABLE records
                ADD CONSTRAINT records_id_constraint
                PRIMARY KEY (id)
            '''
            cursor.execute(query)

            query = '''
            CREATE INDEX records_road ON records USING btree (road)
            '''
            cursor.execute(query)

            query = '''
            CREATE INDEX records_number ON records USING btree (number)
            '''
            cursor.execute(query)

            query = '''
            CREATE INDEX records_zip_code ON records USING btree (zip_code)
            '''
            cursor.execute(query)

            query = '''
            CREATE INDEX records_city ON records USING btree (city)
            '''
            cursor.execute(query)

            connection.commit()


def insert():
    with closing(get_connection()) as connection:
        with open(
            'records.csv',
            'r',
            encoding='iso-8859-1',
            newline='',
        ) as resource:
            with closing(connection.cursor()) as cursor:
                cursor.copy_from(
                    resource,
                    'records',
                    columns=('zip_code', 'city', 'road', 'number'),
                    null='\\n',
                    sep=';',
                    size=999999999,
                )
                connection.commit()


def update():
    with closing(get_connection()) as connection:
        total = get_total('records.csv')
        with open(
            'records.csv',
            'r',
            encoding='iso-8859-1',
            newline='',
        ) as resource:
            rows = csv.reader(resource, delimiter=u';')
            for row in tqdm(rows, total=total):
                with closing(connection.cursor()) as cursor:
                    query = '''
                    SELECT id
                    FROM records
                    WHERE
                        road = %(road)s
                        AND
                        number = %(number)s
                        AND
                        zip_code = %(zip_code)s
                        AND
                        city = %(city)s
                    '''
                    cursor.execute(
                        query,
                        {
                            'road': row[2],
                            'number': row[3],
                            'zip_code': row[0],
                            'city': row[1],
                        },
                    )
                    record = cursor.fetchone()
                    if record:
                        continue
                    query = '''
                    INSERT INTO records (road, number, zip_code, city)
                        VALUES (%(road)s, %(number)s, %(zip_code)s, %(city)s)
                    '''
                    cursor.execute(
                        query,
                        {
                            'road': row[2],
                            'number': row[3],
                            'zip_code': row[0],
                            'city': row[1],
                        },
                    )
                    connection.commit()


def details():
    r = ResQ()
    with closing(get_connection()) as connection:
        total = 0
        with closing(connection.cursor()) as cursor:
            query = '''
            SELECT COUNT(id) AS count
            FROM records
            WHERE details IS NULL
            '''
            cursor.execute(query)
            total = cursor.fetchone()['count']
        with closing(connection.cursor('cursor')) as cursor:
            query = '''
            SELECT *
            FROM records
            WHERE details IS NULL
            '''
            cursor.execute(query)
            for record in tqdm(cursor, total=total):
                r.enqueue(Record, record['id'])


def report():
    with closing(get_connection()) as connection:
        total = 0
        with closing(connection.cursor()) as cursor:
            query = '''
            SELECT COUNT(id) AS count
            FROM records
            '''
            cursor.execute(query)
            total = cursor.fetchone()['count']
        with open(
            'report.csv',
            'w',
            encoding='iso-8859-1',
            newline='',
        ) as resource:
            rows = csv.writer(resource, delimiter=u';')
            rows.writerow([
                'Road',
                'Number',
                'Zip Code',
                'City',
                'Name',
                'Addresses :: Primary',
                'Addresses :: Secondary',
                'Addresses :: Zip Code',
                'Telephone',
                'Fax',
                'Email',
                'Others :: IBAN',
                'Others :: Account Number',
                'Others :: Client Number',
                'Others :: ESCHKG ID',
            ])
            with closing(connection.cursor('cursor')) as cursor:
                query = '''
                SELECT *
                FROM records
                ORDER BY id ASC
                '''
                cursor.execute(query)
                for record in tqdm(cursor, total=total):
                    details = None
                    if 'error' in details:
                        details = record['details']
                    rows.writerow([
                        record['road'],
                        record['number'],
                        record['zip_code'],
                        record['city'],
                        details['name'] if details else '',
                        details['addresses']['primary'] if details else '',
                        details['addresses']['secondary'] if details else '',
                        details['addresses']['zip code'] if details else '',
                        details['tel'] if details else '',
                        details['fax'] if details else '',
                        details['email'] if details else '',
                        details['others']['iban'] if details else '',
                        details['others']['account_number'] if details else '',
                        details['others']['client_number'] if details else '',
                        details['others']['eschkg_id'] if details else '',
                    ])


def workers():
    workers = Khan(pool_size=PYRES, queues=['records'])
    workers.work()


def proxies():
    for index in range(10):
        response = request(
            'GET',
            'http://ifconfig.co/json',
            headers={
                'Content-Type': 'application/json',
            },
            proxies=PROXIES,
        )
        print '{index:02d}: {ip:s}'.format(
            index=index + 1,
            ip=response.json()['ip'],
        )


def test():
    with closing(get_connection()) as connection:
        with closing(connection.cursor('cursor')) as cursor:
            query = '''
            SELECT *
            FROM records
            ORDER BY RANDOM()
            LIMIT 5
            OFFSET 0
            '''
            cursor.execute(query)
            for record in cursor:
                details = get_details(
                    record['road'],
                    record['number'],
                    record['zip_code'],
                    record['city'],
                )
                pprint(details)

if __name__ == '__main__':
    try:
        if argv[1] == 'bootstrap':
            bootstrap()
        if argv[1] == 'insert':
            insert()
        if argv[1] == 'update':
            update()
        if argv[1] == 'details':
            details()
        if argv[1] == 'workers':
            workers()
        if argv[1] == 'report':
            report()
        if argv[1] == 'proxies':
            proxies()
        if argv[1] == 'test':
            test()
    except KeyboardInterrupt:
        pass
    except Exception:
        sentry = get_sentry()
        if sentry:
            sentry.captureException()
