"""Класс SteamTradeBot"""
import csv
from pprint import pprint
from random import choice
from json import load, loads
import time
import re
import sys
import pickle
import requests
import telebot
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.wait import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from requests.exceptions import ProxyError, JSONDecodeError
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from steam.guard import SteamAuthenticator
from csv import DictWriter
from datetime import datetime
from dataclasses import dataclass
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger.remove()
logger.add(
    sys.stderr, format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> |'\
        ' <cyan>{line}</cyan> - <white>{message}</white>")


@dataclass
class Links:
    STEAM_BUFF_LOGIN_LINK: str = ('https://steamcommunity.com/openid/login?openid.mode=checkid_setup&openid.ns=http%3A%'
                                  '2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.realm=https%3A%2F%2Fbuff.163.com%2F&openid'
                                  '.sreg.required=nickname%2Cemail%2Cfullname&openid.assoc_handle=None&openid.return_to'
                                  '=https%3A%2F%2Fbuff.163.com%2Faccount%2Flogin%2Fsteam%2Fverification%3Fback_url%3D%2'
                                  '52Faccount%252Fsteam_bind%252Ffinish&openid.ns.sreg=http%3A%2F%2Fopenid.net%2Fextens'
                                  'ions%2Fsreg%2F1.1&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fident'
                                  'ifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifi'
                                  'er_select')
    STEAM_SKINSTABLE_LOGIN_LINK: str = ('https://steamcommunity.com/openid/login?openid.ns=http%3A%2F%2Fspecs.openid.ne'
                                        't%2Fauth%2F2.0&openid.mode=checkid_setup&openid.return_to=https%3A%2F%2Fskins-'
                                        'table.xyz%2Fsteam%2F%3Flogin&openid.realm=https%3A%2F%2Fskins-table.xyz&openid'
                                        '.ns.sreg=http%3A%2F%2Fopenid.net%2Fextensions%2Fsreg%2F1.1&openid.claimed_id=h'
                                        'ttp%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.identity='
                                        'http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select')
    STEAM_TABLEVV_LOGIN_LINK: str = ('https://steamcommunity.com/openid/login?openid.ns=http://specs.openid.net/auth/2.'
                                     '0&openid.mode=checkid_setup&openid.return_to=https://tablevv.com/api/handle&openi'
                                     'd.realm=https://tablevv.com&openid.identity=http://specs.openid.net/auth/2.0/iden'
                                     'tifier_select&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_selec'
                                     't')
    STEAM: str = "https://steamcommunity.com/"
    STEAM_LOGIN: str = "https://steamcommunity.com/login/home/?goto="


def get_buyed(chain: str) -> dict:
    """
    Подсчет купленных скинов в инвентаре (csv)
    Args:
        chain (str): связка (пр. tm2buff, buff2tm)

    Returns:
        dict: купленные скины из csv
    """
    b = dict()
    with open(f'{chain}.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            if row['skin'] not in b:
                b[row['skin']] = 1
            else:
                b[row['skin']] += 1
    return b


def get_average(history: list) -> float | None:
    """Фильтрация списка продаж
    Args:
        history (list): [время в unix, цена]
    Returns:
        float: средняя по продажам
    """
    one_week = 604800
    if int(history[0][0]) > time.time() - one_week:
        return
    average = sum(el[1] for el in history) / len(history)
    for i, el in enumerate(history):
        price = el[1]
        l_time = el[0]
        if l_time < time.time() - one_week * 3 or price >= average * 2:
            history.pop(i)
    sell_in_2weeks = len(history)
    if sell_in_2weeks > 30:
        prices = [el[1] for el in history]
        average = min(round(sum(prices) / len(prices), 2), (max(prices) + min(prices)) / 2)  # минимальная средняя
        less_than_average = len([price for price in prices if price < average])
        more_than_average = len([price for price in prices if price > average])
        if less_than_average < more_than_average:
            return average
    return


class SteamTradeBot:
    """
    SteamTradeBot by timer
    """
    try:
        with open('./proxies.txt', encoding='utf-8') as file:
            __proxy_base = ''.join(file.readlines()).strip().split('\n')
    except FileNotFoundError:
        logger.error("Необходимо создать файл proxies.txt")
        sys.exit(1)

    __slots__ = (
        '__message', '__percentage', '__tm_api_key', '__tg_bot_token', '__tg_id', '__login', '__password', '__tg_bot',
        '__tm_contenders', '__buff_contenders', '__steam_guard', '__ua', '__session', '__browser', '__wait',
        '__tablevv_cookies', 'rubles_per_yuan')

    def __init__(self, percentage: int = 25):
        """
        Инициализация полей класса
        Args:
            percentage (int): процент завоза
        """
        self.__message = ''

        self.__percentage = percentage
        self.rubles_per_yuan = None

        config = dotenv_values('.env')
        self.__tm_api_key = config["tm_api_key"]
        self.__tg_bot_token = config["tg_bot_token"]
        self.__tg_id = config["tg_id"]
        self.__login = config["login"]
        self.__password = config["password"]

        self.__tg_bot = telebot.TeleBot(self.__tg_bot_token)

        self.__tm_contenders = {}
        self.__buff_contenders = {}

        self.__steam_guard = SteamAuthenticator(load(
            open(f'./{self.__login}.maFile', encoding='utf-8')))

        with open("ua.txt", encoding="utf-8") as file:
            uas = file.readlines()
        self.__ua = re.sub(r"^\s+|\n|\r|\s+$", '', choice(uas))

        self.__tablevv_cookies = open('tablevv_cookies.txt', 'r', encoding='utf-8').read()

        self.__session = requests.session()
        self.__browser = None
        self.__wait = None

    def create_browser(self):
        """Создание нового браузера"""
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.__browser = webdriver.Chrome(options=options)
        self.__browser.maximize_window()
        self.__wait = WebDriverWait(self.__browser, 30)
        self.__browser.get(Links.STEAM)
        self.__browser.delete_all_cookies()
        try:
            for cookie in pickle.load(open('./steam_cookies', 'rb')):
                self.__browser.add_cookie(cookie)
            self.__browser.refresh()
            try:
                self.__wait.until(EC.element_to_be_clickable(
                    (By.XPATH,
                     '//span[@class="pulldown global_action_link persona_name_text_content"]')))
            except TimeoutException:
                raise FileNotFoundError
        except FileNotFoundError:
            self.__browser.delete_all_cookies()
            self.create_steam_cookies()

    def create_steam_cookies(self):
        """Создание steam куки"""
        self.__browser.get(Links.STEAM_LOGIN)
        time.sleep(1)
        self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@type='text']"))).send_keys(self.__login)
        time.sleep(1)
        self.__browser.find_element(
            By.XPATH, "//input[@type='password']").send_keys(self.__password + Keys.ENTER)
        time.sleep(3)
        code = self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//div[@class="newlogindialog_SegmentedCharacterInput_1kJ6q"]')))
        code.find_element(By.TAG_NAME, "input").send_keys(self.__steam_guard.get_code())
        time.sleep(1)

        if self.__wait.until(EC.presence_of_element_located(
                (By.XPATH, '//a[@class="menuitem supernav username persona_name_text_content"]'))):
            pickle.dump(self.__browser.get_cookies(),
                        open("./steam_cookies", "wb"))

    def create_buff_cookies(self):
        """Создание buff куки"""
        self.__browser.get(Links.STEAM_BUFF_LOGIN_LINK)
        self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@class='btn_green_white_innerfade']"))).click()
        if self.__wait.until(EC.url_to_be("https://buff.163.com/account/steam_bind/finish")):
            pickle.dump(self.__browser.get_cookies(),
                        open('./buff_cookies', 'wb'))

    def buff_prep(self):
        """Подготовка Buff163"""

        def get_cny2rub() -> requests.Response:
            """

            Returns:
                ответ от api/user/info

            """
            info = "https://buff.163.com/account/api/user/info"
            payload = {'_': str(time.time()).split('.', maxsplit=1)[0]}
            return self.__session.get(info, json=payload, timeout=30)

        while True:
            try:
                for cookie in pickle.load(open('./buff_cookies', 'rb')):
                    self.__session.cookies.set(cookie["name"], cookie["value"])
                self.__session.headers = self.get_buff_headers()
                response = get_cny2rub()
                if response.json()['code'] != "OK":
                    raise FileNotFoundError
                break
            except FileNotFoundError:
                self.create_browser()
                self.create_buff_cookies()

        self.rubles_per_yuan = round(response.json()['data']['buff_price_currency_rate_base_cny'], 2)
        logger.info(f"1 rub = {self.rubles_per_yuan} yuan")

    def start_buff_2_tm(self):
        """BUFF2TM"""

        def get_minclass_item() -> dict:
            """
            Получаем минимальный market class скина
            Returns:
                dict: item c минимальным class'ом
            """
            while True:
                r = requests.get(
                    f"https://market.csgo.com/api/v2/search-item-by-hash-name?key="
                    f"{self.__tm_api_key}&hash_name={name}")
                if r.ok:
                    return min(r.json()['data'], key=lambda x: x["class"])
                else:
                    print(name)
                    logger.error(r.reason)

        def get_history() -> dict:
            """
            История продаж скина (до 500 продаж)
            Returns:
                dict: [average, history]
            """
            while True:
                response = requests.get(f"https://market.csgo.com/api/ItemHistory/"
                                        f"{item['class']}_{item['instance']}/?key={self.__tm_api_key}")
                try:
                    r = response.json()
                    r.pop('success')
                    r.pop('max')
                    r.pop('min')
                    return r
                except JSONDecodeError:
                    logger.error(response.reason)
                    if response.status_code == 503:
                        time.sleep(10)
                    else:
                        sys.exit(-1)
                except Exception as e:
                    logger.error(e)

        buyed = get_buyed('buff2tm')
        self.buff_prep()
        while True:
            skins = self.get_skins_from_tablevv('buff2tm')
            for name in skins:
                if name in buyed:
                    if buyed[name] >= 3:
                        continue
                item = get_minclass_item()
                if not item:
                    continue
                sell_history = get_history()
                history = [[int(el['l_time']), float(el['l_price']) / 100] for el in sell_history['history']]
                history.reverse()
                average = round(get_average(history), 2)
                if not average:
                    continue
                sell_price = round(average * 0.95, 2)
                buy_price = self.get_buff_id_and_price(name)
                difference = round(sell_price / (buy_price['price'] * self.rubles_per_yuan), 3)
                self.__message += "BUFF2TM" + "\n" + f"Skin: {name}\n" + \
                                  f"Buff price: {round(buy_price['price'] * self.rubles_per_yuan, 2)}\n" + \
                                  f"TM average price: {sell_price} ({average})\n" + \
                                  f"Difference: +{difference}"
                print(self.__message)
                logger.debug("")
                if difference >= (100 + self.__percentage) / 100:
                    buy = self.buff_buy(buy_price['skin_id'], buy_price['price'] * self.rubles_per_yuan)
                    if buy:
                        logger.success("BUY!!!")
                        buy_price = buy['price'] * self.rubles_per_yuan
                        self.__message += f'\n{buy["msg"]}'
                        self.__tg_bot.send_message(self.__tg_id, self.__message)
                        buyed[name] = 1 if name not in buyed else buyed[name] + 1
                        with open(f"buff2tm.csv", 'a', newline='', encoding='utf-8') as csvfile:
                            fieldnames = ['date', 'skin', 'buy_price', 'sell_price']
                            dictwriter_object = DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                            dictwriter_object.writerow({
                                "date": datetime.now().strftime("%d.%m.%Y"),
                                "skin": name,
                                "buy_price": round(buy_price, 2),
                                "sell_price": sell_price})
                self.__message = ''

    def start_tm_2_buff(self):
        """TM2BUFF"""

        def get_history() -> list:
            """Получение истории продажи скина за месяц
            Returns:
                list: [unix время в миллисекундах, цена]
            """
            payload = {
                'game': 'csgo',
                'goods_id': buff['skin_id'],
                'currency': 'RUB',
                'days': 30,
                '_': str(time.time()).split('.', maxsplit=1)[0]
            }
            r = self.__session.get(f'https://buff.163.com/api/market/goods/price_history/buff', json=payload)
            return r.json()['data']['price_history']

        try:
            averages = pickle.load(open('./averages', 'rb'))
        except FileNotFoundError:
            averages = dict()
            pickle.dump(averages, open('./averages', 'wb'))
        self.buff_prep()
        while True:
            skins = self.get_skins_from_tablevv('tm2buff')
            for name in skins:
                if name in averages:
                    average = averages[name]['average']
                else:
                    buff = self.get_buff_id_and_price(name)
                    history = list(map(lambda x: [x[0] // 1000, x[1]],
                                       get_history()))
                    average = round(get_average(history), 2)
                    averages[name] = {'average': average, 'time': time.asctime()}
                if not average:
                    continue
                sell_price = round(average * 0.975, 2)
                buy_price = self.get_market_sell_price_and_market_item_id(name)
                difference = round(buy_price['price'] / sell_price, 3)
                self.__message += "TM2BUFF\n" + f"Skin: {name}\n" + \
                                  f"Buff average price: {sell_price} ({average})\n" + \
                                  f"TM price: {buy_price['price']}\n" + \
                                  f"Difference: -{difference}"
                print(self.__message)
                logger.debug("")
                if difference <= (100 + self.__percentage) / 100:
                    logger.success("BUY!!!")
                    self.__tg_bot.send_message(self.__tg_id, self.__message)
                self.__message = ''

    def start_buff_2_steam(self):
        """BUFF2STEAM"""
        self.create_browser()
        self.buff_prep()
        self.open_skinstable("buff")
        while True:
            skins = self.get_skins_from_skinstable()
            for skin_name in skins:
                buff = self.get_buff_id_and_price(skin_name)
                if skin_name not in self.__buff_contenders:
                    steam = self.get_steam_auto_buy_price(skin_name)
                    self.__buff_contenders[skin_name] = steam
                else:
                    steam = self.__buff_contenders[skin_name]
                difference = (steam * 0.87) / \
                             (buff['price'] * self.rubles_per_yuan)
                print(f"BUFF\n{skin_name}\n"
                      f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n"
                      f"Buff price: {buff['price']:.2f}¥"
                      f" ({self.rubles_per_yuan * buff['price']:.2f}₽)\n"
                      f"Difference is: +{difference:.2f}")
                logger.debug("")
                if difference > (100 + self.__percentage) / 100:
                    buy_price = self.buff_buy(buff['skin_id'], buff['price'])
                    if buy_price:
                        self.__message = (f"BUFF\n{skin_name}\n"
                                          f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n"
                                          f"Buff price: {buff['price']:.2f}¥"
                                          f" ({self.rubles_per_yuan * buy_price:.2f}₽)\n"
                                          f"Difference is: +{difference:.2f}")
                        self.__tg_bot.send_message(self.__tg_id, self.__message)
                        self.__buff_contenders.pop(skin_name)

    def start_tm_2_steam(self):
        """TM2STEAM"""
        self.create_browser()
        self.open_skinstable('tm')
        while True:
            skins = self.get_skins_from_skinstable()
            for skin_name in skins:
                tm_price_and_item_id = self.get_market_sell_price_and_market_item_id(
                    skin_name)
                if skin_name not in self.__tm_contenders:
                    steam = self.get_steam_auto_buy_price(skin_name)
                    self.__tm_contenders[skin_name] = [steam, 0]
                else:
                    self.__tm_contenders[skin_name][1] += 1
                    if self.__tm_contenders[skin_name][1] == 10:
                        steam = self.get_steam_auto_buy_price(skin_name)
                        self.__tm_contenders[skin_name] = [steam, 0]
                    else:
                        steam = self.__tm_contenders[skin_name][0]
                if tm_price_and_item_id is not None and tm_price_and_item_id['skin_id']:
                    tm_sell_id = tm_price_and_item_id['skin_id']
                    tm_sell_price = tm_price_and_item_id['price']
                    difference = (steam * 0.87) / tm_sell_price
                    self.__message = f"{skin_name}\n" + \
                                     f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n" + \
                                     f"TM price: {tm_sell_price:.2f}\n" + \
                                     f"Difference is: +{difference:.2f}"
                    print(self.__message)
                    logger.debug("")
                    if difference > (100 + self.__percentage) / 100:
                        if self.tm_buy(tm_sell_id, tm_sell_price * 100):
                            self.__tm_contenders.pop(skin_name)
                            self.__message = "TM\n" + self.__message
                            self.__tg_bot.send_message(self.__tg_id, self.__message)
                    self.__message = ''

    def open_skinstable(self, market: str):
        """
        Открытие skins-table.xyz в browser
        Args:
            market (str): tm/buff
        """
        self.__browser.get(Links.STEAM_SKINSTABLE_LOGIN_LINK)
        self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@class='btn_green_white_innerfade']"))).click()
        for cookie in pickle.load(
                open('./skinstable_cookies', 'rb')):
            if cookie['name'] == 'first':
                if market == "tm":
                    cookie["value"] = "23"
                if market == "buff":
                    cookie['value'] = "158"
            self.__browser.add_cookie(cookie)
        self.__browser.get("https://skins-table.xyz/table/")

    def get_skins_from_skinstable(self) -> list:
        """
        Получение скинов skins-table.xyz
        Returns:
            list: список скинов
        """
        self.__browser.refresh()
        self.__wait.until(EC.element_to_be_clickable(
            (By.ID, "change1"))).click()  # sort by percentage
        table_skins = self.__wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, '//td[@class="clipboard"]')))
        return [el.text for el in table_skins]

    def get_skins_from_tablevv(self, chain: str) -> list:
        """
        Получение скинов из tablevv.com
        Args:
            chain (string): связка (пр. tm2buff, buff2tm)
        Returns:
            list: список скинов
        """
        link = 'https://tablevv.com/api/table/items-chunk'
        payload = load(open(f"./{chain}.txt", 'r'))
        response = requests.post(link, headers={'cookie': self.__tablevv_cookies}, json=payload, params={"page": 1})
        if response.ok:
            return [skin['n'] for skin in loads(response.content.decode('utf-8'))[
                'items']]
        else:
            logger.info(response.text)

    def tm_buy(self, item_id: str, price: str, trade_link: str = None) -> bool | None:
        """
        Покупка TM скинов
        Args:
            item_id (str): market item_id
            price (str): цена в копейках
            trade_link (str): необязательный параметр, если хочешь отправить на другой аккаунт
        Returns:
            bool: купилось или нет
        """
        link = 'https://market.csgo.com/api/v2/buy?key=' + \
               self.__tm_api_key + '&id=' + \
               item_id + '&price=' + price
        if trade_link:
            link += trade_link
        logger.info(link)
        response = requests.get(link, timeout=10)
        res = response.json()
        logger.info(res['success'])
        if res['success'] is False:
            logger.info(res['error'])
            return None
        return True

    def buff_buy(self, skin_id: int, price: float) -> dict | None:
        """
        Покупка Buff163 скинов
        Args:
            skin_id (int): buff skin_id
            price (float): цена в CNY
        Returns:
            dict: {price, msg}
        """

        def get_current_order() -> dict:
            """
            Получение самого дешевого ордера
            Returns:
                dict: {sell_order_id, price}
            """
            url = 'https://buff.163.com/api/market/goods/sell_order'
            p = {
                'game': 'csgo',
                'goods_id': skin_id,
                'page_num': 1,
                'sort_by': 'price.asc',
                'allow_tradable_cooldown:': 0,
                '_': str(time.time()).split('.', maxsplit=1)[0]
            }
            r = self.__session.get(url, json=p)
            result = r.json()
            return {
                "sell_order_id": result['data']['items'][0]['id'],
                "price": float(result['data']['items'][0]['price'])
            }

        self.__session.headers = self.get_buff_headers()
        current_order = get_current_order()
        if float(current_order["price"]) / price > 1.05:
            return None
        # BUY
        buy = 'https://buff.163.com/api/market/goods/buy'
        payload = {
            'allow_tradable_cooldown': 0,
            'cdkey_id': "",
            'game': "csgo",
            'goods_id': skin_id,
            'pay_method': 3,
            'price': current_order["price"],
            'sell_order_id': current_order["sell_order_id"],
            'token': ""
        }
        self.__session.headers['content-length'] = str(len(payload))
        self.__session.headers['x-csrftoken'] = self.__session.cookies.get_dict()['csrf_token']
        response = self.__session.post(buy, json=payload)
        if response.json()['code'] != "OK":
            print(response.json())
            return None
        bill_order = response.json()['data']['id']

        # ASK_SELLER_TO_SEND_OFFER
        ask_seller_to_send_offer = 'https://buff.163.com/api/market/bill_order/' + \
                                   'ask_seller_to_send_offer'
        payload = {
            "bill_orders": [bill_order],
            "game": "csgo"
        }
        self.__session.headers['content-length'] = str(len(payload))
        self.__session.headers['x-csrftoken'] = self.__session.cookies.get_dict()['csrf_token']
        response = self.__session.post(ask_seller_to_send_offer, json=payload)
        msg = response.json()
        pprint(msg)
        return {'price': float(current_order['price']), 'msg': msg}

    def get_buff_headers(self) -> dict:
        """
        Заголовки для GET запросов
        Returns:
            dict: headers
        """
        headers = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'cookie':
                "; ".join([str(x) + "=" + str(y)
                           for x, y in self.__session.cookies.get_dict().items()]),
            'host': 'buff.163.com',
            'referer': f'https://buff.163.com/',
            'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.__ua,
            'x-requested-with': 'XMLHttpRequest'
        }
        return headers

    def get_steam_auto_buy_price(self, skin_name: str) -> float:
        """
        Получение цены ордера на автопокупку в стиме
        Args:
            skin_name (str): название скина
        Returns:
            float: цена по автобаю на текущий момент
        """
        url = f'https://steamcommunity.com/market/listings/{730}/' + skin_name
        while True:
            proxy = choice(self.__proxy_base)
            proxies = {
                'http': f'https://{proxy}',
                'https': f'https://{proxy}'
            }
            try:
                skin_page = requests.get(url, proxies=proxies, timeout=10)
            except ProxyError:
                logger.info(f"Proxy {proxy.split('@')[1]} is banned")
                self.__tg_bot.send_message(
                    self.__tg_id, f"Proxy {proxy.split('@')[1]} is banned")
                continue
            soup = BeautifulSoup(skin_page.text, 'html.parser')
            try:
                last_script = str(soup.find_all('script')[-1])
            except IndexError as e:
                logger.error(e)
                self.__tg_bot.send_message(self.__tg_id, str(e))
                with open("index.html", 'w', encoding='utf-8') as file:
                    file.write(skin_page.text)
                continue
            except:
                continue
            item_nameid = last_script.rsplit(
                '(', maxsplit=1)[-1].split(');')[0]
            try:
                item_nameid = int(item_nameid)
                break
            except ValueError:
                logger.info(f"Rate limit on {proxy.split('@')[1]}")
                continue
        response = requests.get(
            'https://steamcommunity.com/'
            'market/itemordershistogram?'
            'country=RU&language=english&currency=5'
            f'&item_nameid={item_nameid}&two_factor=0', timeout=10)  # rate limit'а нет
        price = int(response.text.split('"highest_buy_order":')
                    [1].split('\"')[1]) / 100
        return price

    def get_market_sell_price_and_market_item_id(self, skin_name: str) -> dict | list | None:
        # FIXME
        """
        Получение самой дешевой цены и item_id скина на TM'е
        Args:
            skin_name (str): название скина
        Returns:
            dict: {skin_id, price}
            list: Ошибка маркета
            None: Скинов нет
        """
        url = 'https://market.csgo.com/api/v2/' \
              f'search-item-by-hash-name-specific?key={self.__tm_api_key}&hash_name={skin_name}'
        while True:
            try:
                res = requests.get(url, timeout=10).json()
                break
            except JSONDecodeError:
                time.sleep(10)
        if res['success']:
            if len(res['data']) > 0:
                data = res['data'][0]
                market_item_id = data['id']
                price = data['price']
                # Возвращает id предмета и его цену
                return {'skin_id': market_item_id, 'price': price / 100}
            # Скинов нет
            return None
        # Ошибка маркета
        return [res['success'], res['error']]

    def get_buff_id_and_price(self, skin_name: str) -> dict:
        """
        Получение id скина и текущей цены продажи на Buff163
        Args:
            skin_name (str): Название скина
        Returns:
            dict: id, price
        """
        page_num = 1
        while True:
            url = f'https://buff.163.com/api/market/goods?game=csgo&page_num={page_num}&search=' + skin_name

            try:
                response = self.__session.get(url)
                # response может вернуть Too Many Requests (Response <429>)
                result = response.json()
            except JSONDecodeError:
                print(response.status_code)
                print(skin_name)
                pprint(response.content)
                time.sleep(5)
                continue
            except requests.exceptions.ConnectionError:
                time.sleep(5)
                continue

            skin = [item for item in result['data']['items'] if item['market_hash_name'] == skin_name]
            if skin:
                skin = skin[0]
                return {"skin_id": skin['id'], "price": float(skin['sell_min_price'])}
            page_num += 1


if __name__ == "__main__":
    logger.info("CTRL+C для остановки бота или закрыть консоль")
    print("1 - TM2STEAM, 2 - BUFF2STEAM, 3 - BUFF2TM, 4 - TM2BUFF:")
    current_market = int(input())
    print("Процент завоза:")
    perc = int(input())
    stb = SteamTradeBot(percentage=perc)
    if current_market == 1:
        stb.start_tm_2_steam()
    elif current_market == 2:
        stb.start_buff_2_steam()
    elif current_market == 3:
        stb.start_buff_2_tm()
    elif current_market == 4:
        stb.start_tm_2_buff()
