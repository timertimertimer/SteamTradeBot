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
from selenium.webdriver.support import expected_conditions as EC
from requests.exceptions import ProxyError, JSONDecodeError, ConnectionError
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from fake_useragent import UserAgent
import chromedriver_autoinstaller
from steam.guard import SteamAuthenticator
from csv import DictWriter
from datetime import datetime

logger.remove()
logger.add(
    sys.stderr, format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> |'\
        ' <cyan>{line}</cyan> - <white>{message}</white>")


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
        self.__percentage = percentage

        config = dotenv_values('.env')
        self.__tm_api_key = config["tm_api_key"]
        self.__tg_bot_token = config["tg_bot_token"]
        self.__tg_id = config["tg_id"]
        self.__login = config["login"]
        self.__password = config["password"]

        self.__bot = telebot.TeleBot(self.__tg_bot_token)

        self.__tm_contenders = {}
        self.__buff_contenders = {}

        self.__secrets = load(
            open(f'./{self.__login}.maFile', encoding='utf-8'))
        self.__sa = SteamAuthenticator(self.__secrets)
        with open("ua.txt", encoding="utf-8") as file:
            uas = file.readlines()
        self.__ua = re.sub("^\s+|\n|\r|\s+$", '', choice(uas))

        self.__session = requests.session()
        self.__browser = None
        self.__wait = None

    def create_browser(self):
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.__browser = webdriver.Chrome(options=options)
        self.__browser.maximize_window()
        self.__wait = WebDriverWait(self.__browser, 15)
        self.__browser.get("https://steamcommunity.com/")
        self.__browser.delete_all_cookies()
        try:
            for cookie in pickle.load(open('./steam_cookies', 'rb')):
                self.__browser.add_cookie(cookie)
            self.__browser.refresh()
            try:
                self.__wait.until(EC.element_to_be_clickable(
                    (By.XPATH,
                     '//span[@class="pulldown global_action_link persona_name_text_content"]')))
            except:
                raise FileNotFoundError
        except FileNotFoundError:
            self.create_steam_cookies()
    def create_steam_cookies(self):
        """Создание steam куки"""
        self.__browser.get("https://steamcommunity.com/login/home/?goto=login")
        time.sleep(1)
        self.__wait.until(EC.element_to_be_clickable(
            ((By.XPATH, "//input[@type='text']")))).send_keys(self.__login)
        time.sleep(1)
        self.__browser.find_element(
            By.XPATH, "//input[@type='password']").send_keys(self.__password + Keys.ENTER)
        time.sleep(3)
        code = self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//div[@class="newlogindialog_SegmentedCharacterInput_1kJ6q"]')))
        code.find_element(By.TAG_NAME, "input").send_keys(self.__sa.get_code())
        time.sleep(1)
        if self.__wait.until(EC.presence_of_element_located(
                (By.XPATH, '//a[@class="menuitem supernav username persona_name_text_content"]'))):
            pickle.dump(self.__browser.get_cookies(),
                        open("./steam_cookies", "wb"))

    def create_buff_cookies(self):
        """Создание buff куки"""
        with open("./steam_buff_login_link.txt", encoding='utf-8') as file:
            self.__browser.get(file.read().strip())
        self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@class='btn_green_white_innerfade']"))).click()
        if self.__wait.until(EC.url_to_be("https://buff.163.com/account/steam_bind/finish")):
            pickle.dump(self.__browser.get_cookies(),
                        open('./buff_cookies', 'wb'))

    def buff(self):
        """Запуск бота для Buff163"""
        def get_cny2rub():
            info = "https://buff.163.com/account/api/user/info"
            payload = {'_': str(time.time()).split('.', maxsplit=1)[0]}
            response = self.__session.get(info, json=payload, timeout=30)
            return response

        try:
            for cookie in pickle.load(open('./buff_cookies', 'rb')):
                self.__session.cookies.set(cookie["name"], cookie["value"])
            response = get_cny2rub()
            if response.json()['code'] != "OK":
                raise FileNotFoundError
        except FileNotFoundError:
            self.create_buff_cookies()
            for cookie in pickle.load(open('./buff_cookies', 'rb')):
                self.__session.cookies.set(cookie["name"], cookie["value"])

        response = get_cny2rub()
        self.__rubles_per_yuan = round(response.json()['data']['buff_price_currency_rate_base_cny'], 2)
        logger.info(f"1 rub = {self.__rubles_per_yuan} yuan")
        return self.__rubles_per_yuan

    def start_buff_2_tm(self):
        """Buff2TM"""
        buyed = dict()
        with open('buff2tm.csv', newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            for row in reader:
                if row['skin'] not in buyed:
                    buyed[row['skin']] = 1
                else:
                    buyed[row['skin']] += 1
        rubles_per_yuan = self.buff()
        while True:
            skins = self.get_skins_from_tablevv()
            for name in skins:
                if name in buyed and buyed[name] > 4:
                    continue
                items = requests.get(
                    f"https://market.csgo.com/api/v2/search-item-by-hash-name?key={self.__tm_api_key}&hash_name={name}").json()['data']
                while True:
                    try:
                        item = min(items, key=lambda x: x["class"])
                    except ValueError as e:
                        logger.error(e)
                        pprint(items)
                        sys.exit(-1)
                    class_id = item['class']
                    instance_id = item["instance"]

                    sell_history = requests.get(
                        f"https://market.csgo.com/api/ItemHistory/{class_id}_{instance_id}/?key={self.__tm_api_key}").json()
                    try:
                        average_sell_history = int(sell_history['average']) / 100
                        break
                    except KeyError as e:
                        print(e)
                        print(f'https://market.csgo.com/item/{class_id}-{instance_id}-{name}')
                        items.remove(item)
                        if not items:
                            break
                if not items:
                    break
                history = sell_history['history']
                x = []
                y = []
                for i in range(len(history) - 1, -1, -1):
                    price = int(history[i]['l_price']) / 100
                    l_time = int(history[i]['l_time'])
                    if l_time > time.time() - 604800 * 3 and price < average_sell_history * 2:
                        x.append(l_time)
                        y.append(price)
                    else:
                        continue

                sell_in_2weeks = len(y)
                if sell_in_2weeks > 50:
                    sr = min(round(sum(y) / len(y), 2), round((max(y) + min(y)) / 2, 2))

                    less_than_average = len([price for price in y if price < sr])
                    more_than_average = len([price for price in y if price > sr])
                    if less_than_average > more_than_average:
                        continue

                    sell_price = round(sr * 0.95, 2)
                    buff_price = self.get_buff_sell_price_and_skin_id(name)
                    difference = round(sell_price / (buff_price['price'] * rubles_per_yuan), 3)
                    self.__s = f"Skin: {name}\n" +\
                               f"Buff price: {round(buff_price['price'] * rubles_per_yuan, 2)}\n" +\
                               f"TM sr price: {sell_price} ({sr})\n" +\
                               f"Difference: +{difference}"
                    print(self.__s)
                    logger.debug("")
                    if difference >= (100 + self.__percentage) / 100:
                        buy = self.buff_buy(buff_price['skin_id'], buff_price['price'] * rubles_per_yuan)
                        if buy:
                            buy_price = buy['price']
                            self.__s += f'\n{buy["msg"]}'
                            logger.success("BUY!!!")
                            self.__bot.send_message(self.__tg_id, self.__s)
                            with open("buff2tm.csv", 'a', newline='') as csvfile:
                                fieldnames = ['date', 'skin', 'buy_price', 'sell_price']
                                dictwriter_object = DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                                dictwriter_object.writerow({
                                    "date": datetime.now().strftime("%d.%m.%Y"),
                                    "skin": name,
                                    "buy_price": round(float(buy_price) * self.__rubles_per_yuan, 2),
                                    "sell_price": sell_price})

    def start_buff_2_steam(self):
        """Buff2Steam"""
        self.create_browser()
        rubles_per_yuan = self.buff()
        self.open_skinstable("buff")
        while True:
            skins = self.get_skins_from_skinstable()
            for skin_name in skins:
                buff = self.get_buff_sell_price_and_skin_id(skin_name)
                if skin_name not in self.__buff_contenders:
                    steam = self.get_steam_auto_buy_price(skin_name)
                    self.__buff_contenders[skin_name] = steam
                else:
                    steam = self.__buff_contenders[skin_name]
                difference = (steam * 0.87) / \
                             (buff['price'] * rubles_per_yuan)
                print(f"BUFF\n{skin_name}\n" + \
                           f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n" + \
                           f"Buff price: {buff['price']:.2f}¥" + \
                           f" ({rubles_per_yuan * buff['price']:.2f}₽)\n" + \
                           f"Difference is: +{difference:.2f}")
                logger.debug("")
                if difference > (100 + self.__percentage) / 100:
                    buy_price = self.buff_buy(buff['skin_id'], buff['price'])
                    if buy_price:
                        self.__s = f"BUFF\n{skin_name}\n" + \
                           f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n" + \
                           f"Buff price: {buff['price']:.2f}¥" + \
                           f" ({rubles_per_yuan * buy_price:.2f}₽)\n" + \
                           f"Difference is: +{difference:.2f}"
                        self.__bot.send_message(self.__tg_id, self.__s)
                        self.__buff_contenders.pop(skin_name)

    def start_tm_2_steam(self):
        """Запуск бота для TM"""
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
                if tm_price_and_item_id is not None and tm_price_and_item_id[0]:
                    tm_sell_id = tm_price_and_item_id[0]
                    tm_sell_price = tm_price_and_item_id[1]
                    difference = (steam * 0.87) / (tm_sell_price / 100)
                    self.__s = f"{skin_name}\n" + \
                               f"Steam price: {steam:.2f}₽ ({steam * 0.87:.2f})₽\n" + \
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

    def open_tablevv(self):
        """Открытие tablevv.com таблицы"""
        with open("./steam_tablevv_login_link.txt", encoding='utf-8') as file:
            self.__browser.get(file.read().strip())
        self.__wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@class='btn_green_white_innerfade']"))).click()
        self.__browser.get('https://tablevv.com/table')

    def open_skinstable(self, market: str):
        """Открытие skins-table.xyz таблицы"""
        with open("./steam_skinstable_login_link.txt", encoding='utf-8') as file:
            self.__browser.get(file.read().strip())
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
        """Получение скинов из skins-table.xyz таблицы"""
        self.__browser.refresh()
        self.__wait.until(EC.element_to_be_clickable(
            (By.ID, "change1"))).click()  # sort by percentage
        table_skins = self.__wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, '//td[@class="clipboard"]')))
        return [el.text for el in table_skins]

    def get_skins_from_tablevv(self) -> list:
        """Получение скинов из tablevv.com таблицы"""
        link = 'https://tablevv.com/api/table/items-chunk'
        headers = {
            'authority': 'tablevv.com',
            'method': 'POST',
            'path': '/api/table/items-chunk?page=1',
            'scheme': 'https',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-length': '435',
            'content-type': 'application/json',
            'cookie': 'theme=main; token=28b1ce57f78b01e761dd486fd112f7a7; _ga=GA1.1.901986499.1667842625; session=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImN0eSI6IkpXVCJ9.eyJpZCI6Ijc2NTYxMTk4MjIwNjg1OTgwIiwibmJmIjoxNjcxODMxNTI5LCJleHAiOjE2NzQ0MjM1MjksImlhdCI6MTY3MTgzMTUyOX0.ACpDVrpr3q_MqhX8ofGczraAKClWYKSEw-CBaS37YU9hufRmZUwAzF9k3urDia_mMWKP2bQkdGZ2szJVJmRf2uKB2p5GtAWX3iHS5e2DXZHsdIvJI0m40t-CvSMo60luPQ4DVDNMdXqUJHxQ8YA7-oDHA5JHySYu0eM7hc2k9k0ZJD54kkI0Hy9Lb-xH9TSSXze7Od-DuulD4rDkjuqjAH-7uMtcXEvgRzECR4zM79Qzd4Jy-HcQCoL51a6p-Ulii0sYjrRubQ-QdXU-21-pVsnXEhXDdmMUSrhSOBRRDUZsxFD-hmQtFePwVYLDhf5lsrbClzHltYjEyEy-GzldaQ; steamid=76561198220685980; _ga_XQ5E9V1SMC=GS1.1.1672312972.70.1.1672314658.0.0.0',
            'origin': 'https://tablevv.com',
            'platform': 'web',
            'referer': 'https://tablevv.com/table',
            'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
        }
        payload = {
            "filter": {
                "appId": 730, "order": 3, "minSales": 100, "service1": 9, "service2": 17, "countMin1": 1,
                "countMin2": 0,
                "direction": 1, "priceMax1": 0, "priceMax2": 0, "priceMin1": 5, "priceMin2": 0, "profitMax": 102,
                "profitMin": 0, "priceType1": 0, "priceType2": 0, "salesPeriod": 0, "salesService": 17,
                "searchName": "",
                "types":
                    {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0, "6": 1,
                     "7": 0, "8": 0, "9": 0, "10": 0, "11": 1}
            },
            "fee1": {"fee": 2.5, "bonus": 0},
            "fee2": {"fee": 5, "bonus": 0},
            "currency": "USD"
        }
        response = requests.post(link, headers=headers, json=payload, params={"page": 1}, verify=False)
        return [skin['n'] for skin in loads(response.content.decode('utf-8'))['items']]

    def tm_buy(self, item_id: str, price: str, trade_link=None) -> bool | None:
        """Покупка TM скинов"""
        link = 'https://market.csgo.com/api/v2/buy?key=' + \
               self.__tm_api_key + '&id=' + \
               str(item_id) + '&price=' + str(price)
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
        """Покупка Buff163 скинов"""

        def get_headers(session, skin_id):
            """Header'ы для GET запросов"""
            headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-encoding': 'gzip, deflate, br',
                'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'cookie':
                    "; ".join([str(x) + "=" + str(y)
                               for x, y in session.cookies.get_dict().items()]),
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
                '_': str(time.time()).split('.', maxsplit=1)[0]
            }
            response = session.get(
                url, json=payload, headers=get_headers(session, skin_id))
            result = response.json()
            return {
                "sell_order_id": result['data']['items'][0]['id'],
                "price": float(result['data']['items'][0]['price'])
            }

        current_order = get_current_order(skin_id, self.__session)
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
        response = self.__session.post(
            buy, json=payload, headers=post_headers(self.__session, skin_id, payload))
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
        response = self.__session.post(ask_seller_to_send_offer,
                                       json=payload,
                                       headers=post_headers(
                                           self.__session,
                                           skin_id,
                                           payload
                                       ))
        msg = response.json()
        pprint(msg)
        return {'price': current_order['price'], 'msg': msg}

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
                skin_page = requests.get(url, proxies=proxies, timeout=10)
            except ProxyError:
                logger.info(f"Proxy {proxy.split('@')[1]} is banned")
                self.__bot.send_message(
                    self.__tg_id, f"Proxy {proxy.split('@')[1]} is banned")
                continue
            soup = BeautifulSoup(skin_page.text, 'html.parser')
            try:
                last_script = str(soup.find_all('script')[-1])
            except IndexError as error:
                logger.error(error)
                self.__bot.send_message(self.__tg_id, error)
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

    def get_market_sell_price_and_market_item_id(self, skin_name: str) -> list | None:
        """Получение самой дешевой цены и item_id скина на TM'е"""
        url = 'https://market.csgo.com/api/v2/' \
              f'search-item-by-hash-name-specific?key={self.__tm_api_key}&hash_name={skin_name}'
        while True:
            try:
                res = requests.get(url, timeout=10).json()
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
            # Скинов нет
            return None
        # Ошибка маркета
        return [res['success'], res['error']]

    def get_buff_sell_price_and_skin_id(self, skin_name) -> dict:
        """Получение самой дешевой цены и skin_id скина на Buff163'е"""
        url = 'https://buff.163.com/api/market/goods?game=csgo&page_num=1&search=' + skin_name
        response = self.__session.get(url)
        try:
            result = response.json()
        except JSONDecodeError as e:
            logger.error(e)
            print(response.status_code)
            pprint(response.content)
            sys.exit(-1)
        skin = {}
        for item in result['data']['items']:
            if item['market_hash_name'] == skin_name:
                skin = item
                break
        return {"skin_id": skin['id'], "price": float(skin['sell_min_price'])}


if __name__ == "__main__":
    logger.info("CTRL+C для остановки бота или закрыть консоль")
    print("1 - tm to steam, 2 - buff to steam, 3 - buff to tm:")
    current_market = int(input())
    perc = int(input("Процент завоза:"))
    stb = SteamTradeBot(percentage=perc)
    if current_market == 1:
        stb.start_tm_2_steam()
    elif current_market == 2:
        stb.start_buff_2_steam()
    elif current_market == 3:
        while True:
            try:
                stb.start_buff_2_tm()
            except ConnectionError as e:
                print(e)
                time.sleep(15)
