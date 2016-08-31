# -*- coding: utf-8 -*-

from io import open
from mmap import mmap

from fake_useragent import UserAgent
from psycopg2 import connect
from psycopg2.extras import DictCursor
from raven import Client
from requests import Session
from scrapy.selector import Selector

from settings import POSTGRESQL, PROXIES, SENTRY


def get_details(road, number, zip_code, city):
    user_agent = UserAgent()

    session = Session()

    response = session.request(
        'POST',
        'http://www.egeli-informatik.ch/prd/wp-admin/admin-ajax.php',
        data={
            'action': 'aemterfinden_suggestions',
            'place': u'{road:s} {number:s} {zip_code:s} {city:s}'.format(
                road=road,
                number=number,
                zip_code=zip_code,
                city=city,
            ),
        },
        headers={
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'DNT': '1',
            'Host': 'www.egeli-informatik.ch',
            'Origin': 'http://www.egeli-informatik.ch',
            'Referer': (
                'http://www.egeli-informatik.ch/unsere_loesungen/'
                'forderungsmanagement/aemterfinden/'
            ),
            'User-Agent': user_agent.random,
            'X-Requested-With': 'XMLHttpRequest',
        },
        proxies=PROXIES,
    )
    if not response:
        return {
            'error': 'if not response #1',
        }

    json = response.json()

    if not json:
        return {
            'error': 'if not json',
        }

    if 'data' not in json:
        return {
            'error': 'if data not json',
        }

    if not json['data']:
        return {
            'error': 'if not json[data]',
        }

    response = session.request(
        'POST',
        'http://www.egeli-informatik.ch/prd/wp-admin/admin-ajax.php',
        data={
            'action': 'aemterfinden_result',
            'addressObject[Aktiv]':
                json['data'][0]['Aktiv'],
            'addressObject[AlternativeSuchbegriffe][string]':
                json['data'][0]['AlternativeSuchbegriffe']['string'],
            'addressObject[AlternativeSuchbegriffeAsSearchString]':
                json['data'][0]['AlternativeSuchbegriffeAsSearchString'],
            'addressObject[AlternativeSuchbegriffeAsString]':
                json['data'][0]['AlternativeSuchbegriffeAsString'],
            'addressObject[BfsNr]':
                json['data'][0]['BfsNr'],
            'addressObject[HausKey]':
                json['data'][0]['HausKey'],
            'addressObject[HausNummer]':
                json['data'][0]['HausNummer'],
            'addressObject[HausNummerAlpha]':
                json['data'][0]['HausNummerAlpha'],
            'addressObject[Kanton]':
                json['data'][0]['Kanton'],
            'addressObject[Land]':
                json['data'][0]['Land'],
            'addressObject[NameComplete]':
                json['data'][0]['NameComplete'],
            'addressObject[Onrp]':
                json['data'][0]['Onrp'],
            'addressObject[Ort]':
                json['data'][0]['Ort'],
            'addressObject[Postleitzahl]':
                json['data'][0]['Postleitzahl'],
            'addressObject[Quartier]':
                json['data'][0]['Quartier'],
            'addressObject[SprachCode]':
                json['data'][0]['SprachCode'],
            'addressObject[Stadtkreis]':
                json['data'][0]['Stadtkreis'],
            'addressObject[StrassenName]':
                json['data'][0]['StrassenName'],
            'amtTyp': 'CO',
        },
        headers={
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'DNT': '1',
            'Host': 'www.egeli-informatik.ch',
            'Origin': 'http://www.egeli-informatik.ch',
            'Referer': (
                'http://www.egeli-informatik.ch/unsere_loesungen/'
                'forderungsmanagement/aemterfinden/'
            ),
            'User-Agent': user_agent.random,
            'X-Requested-With': 'XMLHttpRequest',
        },
        proxies=PROXIES,
    )
    if not response:
        return {
            'error': 'if not response #2',
        }

    details = {
        'name': '',
        'addresses': {
            'primary': '',
            'secondary': '',
            'zip_code': '',
        },
        'tel': '',
        'fax': '',
        'email': '',
        'others': {
            'iban': '',
            'account_number': '',
            'client_number': '',
            'eschkg_id': '',
        }
    }

    selector = Selector(text=response.text)

    try:
        details['name'] = selector.xpath(
            u'//li/div[@class="result"]/h2/text()',
        ).extract()[0]
    except IndexError:
        pass

    try:
        details['addresses']['primary'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="address_primary"]/text()',
        ).extract()[0]
    except IndexError:
        pass

    try:
        details['addresses']['secondary'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="address_secondary"]/text()',
        ).extract()[0]
    except IndexError:
        pass

    try:
        details['addresses']['zip_code'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="address_zip_code"]/text()',
        ).extract()[0]
    except IndexError:
        pass

    try:
        details['tel'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="phone_primary"]/text()',
        ).extract()[0]
        if details['tel']:
            details['tel'] = get_string(details['tel'])
    except IndexError:
        pass

    try:
        details['fax'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="phone_secondary"]/text()',
        ).extract()[0]
        if details['fax']:
            details['fax'] = get_string(details['fax'])
    except IndexError:
        pass

    try:
        details['email'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="email"]/a/text()',
        ).extract()[0]
    except IndexError:
        pass

    try:
        details['others']['iban'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="bankAccountIban"]/text()',
        ).extract()[0]
        if details['others']['iban']:
            details['others']['iban'] = get_string(
                details['others']['iban'],
            )
    except IndexError:
        pass

    try:
        details['others']['account_number'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="account"]/text()',
        ).extract()[0]
        if details['others']['account_number']:
            details['others']['account_number'] = get_string(
                details['others']['account_number'],
            )
    except IndexError:
        pass

    try:
        details['others']['client_number'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="client_number"]/text()',
        ).extract()[0]
        if details['others']['client_number']:
            details['others']['client_number'] = get_string(
                details['others']['client_number'],
            )
    except IndexError:
        pass

    try:
        details['others']['eschkg_id'] = selector.xpath(
            u'//li/div[@class="result"]/div[@class="column"]/'
            'p[@class="eschkg_id"]/text()',
        ).extract()[0]
        if details['others']['eschkg_id']:
            details['others']['eschkg_id'] = get_string(
                details['others']['eschkg_id'],
            )
    except IndexError:
        pass

    return details


def get_connection():
    connection = connect(
        host=POSTGRESQL['host'],
        port=POSTGRESQL['port'],
        user=POSTGRESQL['user'],
        password=POSTGRESQL['password'],
        database=POSTGRESQL['database'],
        cursor_factory=DictCursor,
    )
    return connection


def get_sentry():
    if SENTRY:
        sentry = Client(SENTRY)
        return sentry


def get_string(string):
    string = string.split(':', 1)
    string = string[-1]
    string = string.strip()
    return string


def get_total(file):
    lines = 0
    with open(file, 'r+') as resource:
        buffer = mmap(resource.fileno(), 0)
        while buffer.readline():
            lines += 1
    return lines
