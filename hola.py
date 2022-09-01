from pprint import pprint
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from requests.exceptions import ProxyError
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from random import choice
from json import load
from steam.guard import SteamAuthenticator
from fake_useragent import UserAgent
from ctypes import windll
import requests
import time
import telebot
import pickle
import chromedriver_autoinstaller
import sys

logger.remove()
logger.add(
    sys.stderr, format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <cyan>{line}</cyan> - <white>{message}</white>")
windll.kernel32.SetConsoleTitleW('SteamTradeBot | by timer')


class SteamTradeBot():
    """Класс для запуска бота"""

    def __init__(self, percentage=25):
        """Инициализация полей класса"""
        self.__s = ''
        try:
            with open('./proxies.txt', encoding='utf-8') as file:
                self.proxy_base = ''.join(file.readlines()).strip().split('\n')
        except FileNotFoundError:
            logger.error("Необходимо создать файл proxies.txt")
            sys.exit(1)
        self.__main_cookies = [{'domain': 'skins-table.xyz',
                                'expiry': 253402300799,
                                'httpOnly': False,
                                'name': 'per1_from',
                                'path': '/table/',
                                'secure': False,
                                'value': '5.00'},  # Сортировка минимальной разницы в процентах между площадками
                               {'domain': 'skins-table.xyz',
                                'expiry': 253402300799,
                                'httpOnly': False,
                                'name': 'first',
                                'path': '/table/',
                                'secure': False,
                                'value': '0'},  # Buff - 158, TM - 23
                               {'domain': 'skins-table.xyz',
                                'expiry': 253402300799,
                                'httpOnly': False,
                                'name': 'sc1',
                                'path': '/table/',
                                'secure': False,
                                'value': '10'},  # Минимальное кол-во продаж за неделю в Steam
                               {'domain': 'skins-table.xyz',
                                'expiry': 253402300799,
                                'httpOnly': False,
                                'name': 'refresh_checkbox',
                                'path': '/table/',
                                'secure': False,
                                'value': ''},
                               {'domain': 'skins-table.xyz',
                                'expiry': 253402300799,
                                'httpOnly': False,
                                'name': 'tm1',
                                'path': '/table/',
                                'secure': False,
                                'value': '10'},  # Минимальное кол-во продаж за неделю на TM
                               {'domain': 'skins-table.xyz',
                                'expiry': 253402300799,
                                'httpOnly': False,
                                'name': 'price1_from',
                                'path': '/table/',
                                'secure': False,
                                'value': '3.00'},  # Минимальная цена в долларах
                               {'domain': 'skins-table.xyz',
                                'expiry': 253402300799,
                                'httpOnly': False,
                                'name': 'second',
                                'path': '/table/',
                                'secure': False,
                                'value': '53'}]  # Steam(AUTO) - 53
        self.__percentage = percentage

        config = dotenv_values('.env')
        self.__tm_api_key = config["tm_api_key"]
        self.__tg_bot_token = config["tg_bot_token"]
        self.__tg_id = config["tg_id"]
        self.__login = config["login"]
        self.__password = config["password"]

        self.__bot = telebot.TeleBot(self.__tg_bot_token)
        # self.__bot.config["api_key"] = self.__tg_bot_token

        self.__tm_contenders = dict()
        self.__buff_contenders = dict()

        self.__secrets = load(open(f'./{self.__login}.maFile'))
        self.__sa = SteamAuthenticator(self.__secrets)
        self.__ua = UserAgent().random

        chromedriver_autoinstaller.install()
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.__browser = webdriver.Chrome(options=options)
        self.__browser.maximize_window()
        self.__wait = WebDriverWait(self.__browser, 60)
        self.__browser.get("https://steamcommunity.com/")
        self.__browser.delete_all_cookies()
        try:
            for cookie in pickle.load(open('./steam_cookies', 'rb')):
                self.__browser.add_cookie(cookie)
            self.__browser.refresh()
            try:
                self.__wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//span[@class="pulldown global_action_link persona_name_text_content"]')))
            except:
                raise FileNotFoundError
        except FileNotFoundError:
            self.create_steam_cookies()

    def create_steam_cookies(self):  # TODO: авторизация steam через requests
        self.__browser.get("https://steamcommunity.com/login")
        time.sleep(1)
        self.__wait.until(EC.element_to_be_clickable(
            ((By.NAME, "username")))).send_keys(self.__login)
        time.sleep(1)
        self.__browser.find_element(
            By.NAME, "password").send_keys(self.__password + Keys.ENTER)
        time.sleep(3)
        self.__wait.until(EC.element_to_be_clickable(
            (By.ID, "twofactorcode_entry"))).send_keys(self.__sa.get_code())
        self.__browser.find_element(
            By.ID, "twofactorcode_entry").send_keys(Keys.ENTER)
        time.sleep(1)
        if self.__wait.until(EC.presence_of_element_located((By.XPATH, '//a[@class="menuitem supernav username persona_name_text_content"]'))):
            pickle.dump(self.__browser.get_cookies(),
                        open("./steam_cookies", "wb"))

    def create_buff_cookies(self):
        self.__browser.get("https://steamcommunity.com/openid/login?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.realm=https%3A%2F%2Fbuff.163.com%2F&openid.sreg.required=nickname%2Cemail%2Cfullname&openid.assoc_handle=None&openid.return_to=https%3A%2F%2Fbuff.163.com%2Faccount%2Flogin%2Fsteam%2Fverification%3Fback_url%3D%252Faccount%252Fsteam_bind%252Ffinish&openid.ns.sreg=http%3A%2F%2Fopenid.net%2Fextensions%2Fsreg%2F1.1&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select")
        self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@class='btn_green_white_innerfade']"))).click()
        if self.__wait.until(EC.url_to_be("https://buff.163.com/account/steam_bind/finish")):
            pickle.dump(self.__browser.get_cookies(),
                        open('./buff_cookies', 'wb'))

    def start_buff(self):
        """Запуск бота для Buff163"""
        response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js")
        self.__rubles_per_yuan = response.json()["Valute"]["CNY"]["Value"] / 10
        logger.info("1 rub = " + str(self.__rubles_per_yuan) + " yuan")

        self.__session = requests.session()
        try:
            for cookie in pickle.load(open('./buff_cookies', 'rb')):
                self.__session.cookies.set(cookie["name"], cookie["value"])
            info = "https://buff.163.com/account/api/user/info"
            payload = {'_': str(time.time()).split('.')[0]}
            response = self.__session.get(info, json=payload)
            if response.json()['code'] != "OK":
                raise FileNotFoundError
        except FileNotFoundError:
            self.create_buff_cookies()
            for cookie in pickle.load(open('./buff_cookies', 'rb')):
                self.__session.cookies.set(cookie["name"], cookie["value"])

        self.open_skinstable("buff")
        while True:
            skins = self.get_skins()
            for skin_name in skins:
                buff = self.get_buff_sell_price_and_skin_id(skin_name)
                if skin_name not in self.__buff_contenders.keys():
                    steam = self.get_steam_auto_buy_price(skin_name)
                    self.__buff_contenders[skin_name] = steam
                else:
                    steam = self.__buff_contenders[skin_name]
                difference = (steam * 0.87) / \
                    (buff['price'] * self.__rubles_per_yuan)
                self.__s = f"BUFF\n{skin_name}\n" + f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n" + \
                    f"Buff price: {buff['price']:.2f}¥ ({self.__rubles_per_yuan * buff['price']:.2f}₽)\n" + \
                    f"Difference is: +{difference:.2f}"
                print(self.__s)
                logger.debug("")
                if difference > (100 + self.__percentage) / 100:
                    self.__bot.send_message(self.__tg_id, self.__s)
                    self.buff_buy(buff['skin_id'], buff['price'])
                    self.__buff_contenders.pop(skin_name)
                else:
                    pass
                self.__s = ''

    def start_tm(self):
        """Запуск бота для TM"""
        self.open_skinstable('tm')
        while True:
            skins = self.get_skins()
            for skin_name in skins:
                tm = self.get_market_sell_price_and_market_item_id(skin_name)
                if skin_name not in self.__tm_contenders.keys():
                    steam = self.get_steam_auto_buy_price(skin_name)
                    self.__tm_contenders[skin_name] = [steam, 0]
                else:
                    self.__tm_contenders[skin_name][1] += 1
                    if self.__tm_contenders[skin_name][1] == 10:
                        steam = self.get_steam_auto_buy_price(skin_name)
                        self.__tm_contenders[skin_name] = [steam, 0]
                    else:
                        steam = self.__tm_contenders[skin_name][0]
                if tm is not None and tm[0]:
                    tm_sell_id = tm[0]
                    tm_sell_price = tm[1]
                    difference = (steam * 0.87) / (tm_sell_price / 100)
                    self.__s = f"{skin_name}\n" + f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n" + \
                        f"TM price: {tm_sell_price / 100:.2f}\n" + \
                        f"Difference is: +{difference:.2f}"
                    print(self.__s)
                    logger.debug("")
                    if difference > (100 + self.__percentage) / 100:
                        if self.tm_buy(tm_sell_id, tm_sell_price):
                            self.__tm_contenders.pop(skin_name)
                            self.__s = "TM\n" + self.__s
                            self.__bot.send_message(self.__tg_id, self.__s)
                    self.__s = ''

    def open_skinstable(self, market: str):
        """Открытие skins-table.xyz таблицы"""
        self.__browser.get("https://steamcommunity.com/openid/login?openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.mode=checkid_setup&openid.return_to=https%3A%2F%2Fskins-table.xyz%2Fsteam%2F%3Flogin&openid.realm=https%3A%2F%2Fskins-table.xyz&openid.ns.sreg=http%3A%2F%2Fopenid.net%2Fextensions%2Fsreg%2F1.1&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select")
        self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@class='btn_green_white_innerfade']"))).click()
        for el in self.__main_cookies:
            if el['name'] == 'first':
                if market == "tm":
                    el["value"] = "23"
                if market == "buff":
                    el['value'] = "158"
            self.__browser.add_cookie(el)
        self.__browser.get("https://skins-table.xyz/table/")

    def get_skins(self) -> list:
        """Получение скинов из таблицы"""
        self.__browser.refresh()
        self.__wait.until(EC.element_to_be_clickable(
            (By.ID, "change1"))).click()  # sort by percentage
        table_skins = self.__wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, '//td[@class="clipboard"]')))
        return [el.text for el in table_skins]

    def tm_buy(self, item_id: str, price: str, trade_link=None) -> None:
        """Покупка TM скинов"""
        link = f'https://market.csgo.com/api/v2/buy?key=' + \
            self.__tm_api_key + '&id=' + \
            str(item_id) + '&price=' + str(price)
        if trade_link:
            link += trade_link
        logger.info(link)
        r = requests.get(link)
        res = r.json()
        logger.info(res['success'])
        if res['success'] is False:
            logger.info(res['error'])
            return False
        else:
            return True

    def buff_buy(self, skin_id: int, price: float) -> None:
        """Покупка Buff163 скинов"""
        def get_headers(session, skin_id):
            """Headers'ы для GET запросов"""
            headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-encoding': 'gzip, deflate, br',
                'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'cookie': "; ".join([str(x)+"="+str(y) for x, y in session.cookies.get_dict().items()]),
                'host': 'buff.163.com',
                'referer': f'https://buff.163.com/goods/{skin_id}?from=market',
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

        def post_headers(session, skin_id, payload):
            """Headers'ы для POST запросов"""
            headers = get_headers(session, skin_id)
            headers['content-length'] = str(len(payload))
            headers['x-csrftoken'] = session.cookies.get_dict()['csrf_token']
            return headers

        def get_current_order(skin_id, session):
            """Получение самого дешевого ордера"""
            url = 'https://buff.163.com/api/market/goods/sell_order'
            payload = {
                'game': 'csgo',
                'goods_id': skin_id,
                'page_num': 1,
                'sort_by': 'price.asc',
                'allow_tradable_cooldown:': 0,
                '_': str(time.time()).split('.')[0]
            }
            response = session.get(
                url, json=payload, headers=get_headers(session, skin_id))
            result = response.json()
            return {"sell_order_id": result['data']['items'][0]['id'], "price": result['data']['items'][0]['price']}

        current_order = get_current_order(skin_id, self.__session)
        if float(current_order["price"]) > price:
            self.__bot.send_message(self.__tg_id, self.__s)
        elif float(current_order["price"]) / price > 1.05:
            return
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
        response = self.__session.post(
            buy, json=payload, headers=post_headers(self.__session, skin_id, payload))
        if response.json()['code'] is not "OK":
            print(response.json())
            return
        bill_order = response.json()['data']['id']

        # ASK_SELLER_TO_SEND_OFFER
        ask_seller_to_send_offer = 'https://buff.163.com/api/market/bill_order/ask_seller_to_send_offer'
        payload = {
            "bill_orders": [bill_order],
            "game": "csgo"
        }
        response = self.__session.post(ask_seller_to_send_offer,
                                       json=payload, headers=post_headers(self.__session, skin_id, payload))
        pprint(response.json())

    def get_steam_auto_buy_price(self, skin_name: str) -> float:
        """Получение цены ордера на автопокупку в стиме"""
        url = f'https://steamcommunity.com/market/listings/{730}/' + skin_name
        while True:
            proxy = choice(self.proxy_base)
            proxies = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            try:
                skin_page = requests.get(url, proxies=proxies)
            except ProxyError:
                logger.info(f"Proxy {proxy.split('@')[1]} is banned")
                self.__bot.send_message(
                    self.__tg_id, f"Proxy {proxy.split('@')[1]} is banned")
                continue
            soup = BeautifulSoup(skin_page.text, 'html.parser')
            try:
                last_script = str(soup.find_all('script')[-1])
            except IndexError as e:
                logger.error(e)
                self.__bot.send_message(self.__tg_id, e)
                open("index.html", 'w').write(skin_page.text)
                continue
            item_nameid = last_script.split('(')[-1].split(');')[0]
            try:
                item_nameid = int(item_nameid)
                break
            except:
                logger.info(f"Rate limit on {proxy.split('@')[1]}")
                continue
        r = requests.get(
            f'https://steamcommunity.com/'
            f'market/itemordershistogram?country=RU&language=english&currency=5&item_nameid={item_nameid}&two_factor=0')  # rate limit'а нет
        price = int(r.text.split('"highest_buy_order":')
                    [1].split('\"')[1]) / 100
        return price

    def get_market_sell_price_and_market_item_id(self, skin_name: str) -> list | None:
        """Получение самой дешевой цены и item_id скина на TM'е"""
        url = f'https://market.csgo.com/api/v2/search-item-by-hash-name-specific?key={self.__tm_api_key}&hash_name={skin_name}'
        while True:
            try:
                res = requests.get(url).json()
                break
            except:
                time.sleep(10)
        if res['success']:
            if len(res['data']) > 0:
                data = res['data'][0]
                market_item_id = data['id']
                price = data['price']
                # Возвращает id предмета и его цену
                return [market_item_id, price]
            else:
                # Скинов нет
                return None
        else:
            # Ошибка маркета
            return [res['success'], res['error']]

    def get_buff_sell_price_and_skin_id(self, skin_name) -> dict:
        """Получение самой дешевой цены и skin_id скина на Buff163'е"""
        url = 'https://buff.163.com/api/market/goods?game=csgo&page_num=1&search=' + skin_name
        response = self.__session.get(url)
        result = response.json()
        skin = dict()
        for el in result['data']['items']:
            if el['market_hash_name'] == skin_name:
                skin = el
                break
        return {"skin_id": skin['id'], "price": float(skin['sell_min_price'])}


if __name__ == "__main__":
    logger.info("CTRL+C для остановки бота или закрыть консоль")
    market = int(input("1 - tm to steam, 2 - buff to steam:"))
    perc = int(input("Процент завоза:"))
    if market == 1:
        stb = SteamTradeBot(percentage=perc)
        stb.start_tm()
    elif market == 2:
        stb = SteamTradeBot(percentage=perc)
        stb.start_buff()
