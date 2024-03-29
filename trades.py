"""Вывод текущих трейдов в тг"""
from time import sleep
from dotenv import dotenv_values
from requests import get
import telebot

config = dotenv_values('.env')
tm_api_key = config['tm_api_key']
tg_bot_token = config["tg_bot_token"]
tg_id = config["tg_id"]
bot = telebot.TeleBot(tg_bot_token)
try:
    while True:
        response = get(
            'https://market.csgo.com/api/v2/trades/?key=' + tm_api_key)
        print(response.json())
        if response.json()['success']:
            bot.send_message(tg_id, "Confirm trades")
            sleep(100)
        else:
            sleep(5)
except KeyboardInterrupt:
    pass
