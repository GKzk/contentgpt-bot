# coding: utf-8

import logging
from hashlib import md5
from datetime import datetime
from urllib.parse import parse_qs
import xml.etree.ElementTree as ET


def get_logger(log_name='yandex_kassa'):
    """Получение логгера."""
    return logging.getLogger(log_name)


class BaseYandexKassa:
    """Базовый класс."""

    def __init__(self, shop_id, sc_id, shop_password, raw_data, log_name=None):
        self.logger = get_logger(log_name) if log_name else get_logger()
        self.shop_id = shop_id
        self.sc_id = sc_id
        self.shop_password = shop_password
        self.raw_data = parse_qs(raw_data)
        self.cleaning_data = self.full_clean()
        self.action = self.cleaning_data['action']

    def full_clean(self):
        """Проводим данные к читаемому виду."""
        cleaning_data = {}

        for key, value in self.raw_data.items():
            # delete: \\\n
            cleaning_data[key] = value[0].strip().strip('\\').strip()

        fields = [
            # ['requestDatetime', ''],
            ['action', str],
            ['md5', str],
            ['shopId', int],
            ['shopArticleId', int],
            ['invoiceId', int],
            ['orderNumber', str],
            ['scid', int],
            ['customerNumber', str],
            # ['orderCreatedDatetime', ''],
            # Decimal
            ['orderSumAmount', str],
            ['orderSumCurrencyPaycash', int],
            ['orderSumBankPaycash', int],
            # Decimal
            ['shopSumAmount', str],
            ['shopSumCurrencyPaycash', int],
            ['shopSumBankPaycash', int],
            ['paymentPayerCode', int],
            ['paymentType', str],
        ]

        for field, type_ in fields:
            try:
                cleaning_data[field] = type_(cleaning_data[field])
            except KeyError:
                continue

        self.logger.info('clean data: %s', cleaning_data)

        return cleaning_data

    def check_shop(self):
        """
        Проверка тому ли магазину пришел запрос.

        :return: bool
        """
        if self.shop_id == self.cleaning_data['shopId']:
            if self.sc_id == self.cleaning_data['scid']:
                return True

        self.logger.info('unknown shop IDs')
        return False

    def check_md5_sum(self, order_sum):
        """
        Генерация MD5 суммы пришедших от Yandex параметров, как указано в
        документации:

            action;orderSumAmount;orderSumCurrencyPaycash;orderSumBankPaycash;
            shopId;invoiceId;customerNumber;shopPassword

        :return: bool
        """

        md5_fields = [
            self.cleaning_data['action'],
            order_sum,
            self.cleaning_data['orderSumCurrencyPaycash'],
            self.cleaning_data['orderSumBankPaycash'],
            self.shop_id,
            self.cleaning_data['invoiceId'],
            self.cleaning_data['customerNumber'],
            self.shop_password
        ]

        md5_str = ';'.join(map(str, md5_fields))
        md5_sum = md5(md5_str.encode()).hexdigest().upper()

        if md5_sum == self.cleaning_data['md5']:
            self.logger.info('the MD5 order and the MD5 yandex is equal')
            return True
        else:
            self.logger.warning(
                'the MD5 order and the MD5 yandex is not equal'
            )
            return False

    def get_customer_number(self):
        """ Идентификатор плательщика на стороне магазина """
        return self.cleaning_data.get('customerNumber', None)

    def get_order_sum(self):
        """ Сумма заказа """
        return self.cleaning_data.get('orderSumAmount', None)

    def get_shop_sum(self):
        """ Сумма выплачиваемая магазину с вычетом комиссии Yandex """
        return self.cleaning_data.get('shopSumAmount', None)

    def check_action(self):
        """Метод проверки события, нужна реализация в дочерних классах."""
        raise NotImplementedError()

    def _get_response(self, **kwargs):
        attrs = {
            'performedDatetime': datetime.now().isoformat(),
            'code': str(kwargs.get('code')),
            'invoiceId': str(self.cleaning_data.get('invoiceId')),
            'shopId': str(self.shop_id)
        }

        if kwargs.get('message'):
            attrs.update({'message': kwargs.get('message')})

        if kwargs.get('techMessage'):
            attrs.update({'techMessage': kwargs.get('techMessage')})

        root = {
            'checkOrder': 'checkOrderResponse',
            'paymentAviso': 'paymentAvisoResponse'
        }

        res_xml = ET.Element(root[self.action], **attrs)

        return ET.tostring(res_xml)

    def get_response(self, code, message=None, tech_message=None):
        """Получение ответа для яндекса."""
        return self._get_response(
            **{'code': code, 'message': message, 'techMessage': tech_message})


class CheckOrder(BaseYandexKassa):
    """
    https://tech.yandex.ru/money/doc/payment-solution/payment-notifications/payment-notifications-check-docpage/
    """
    def __init__(self, *args, **kwargs):
        super(CheckOrder, self).__init__(*args, **kwargs)

    def check_action(self):
        """Проверяем событие."""
        return self.action == 'checkOrder'


class PaymentAviso(BaseYandexKassa):
    """
    https://tech.yandex.ru/money/doc/payment-solution/payment-notifications/payment-notifications-aviso-docpage/
    """

    def __init__(self, *args, **kwargs):
        super(PaymentAviso, self).__init__(*args, **kwargs)

    def check_action(self):
        """Проверяем событие."""
        return self.action == 'paymentAviso'
