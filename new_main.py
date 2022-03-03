from laundry_bot_logics import UltimateClassThatContainsEverythingForReply
from configparser import ConfigParser
from flask import Flask, request
from random import randint
from time import sleep
import sqlite3 as sl
import subprocess
import requests
import telebot
import json

"""
тут происходит основная магия взаимодействия с api разных мессенджеров
"""

datetime_format = '%d.%m.%Y %H:%M'
time_format = '%H:%M'
tz = 5  # часовой пояс (UTC+5), в системе по UTC


# для чтения секции из config.ini
def read_config(section, filename='config.ini'):
    parser = ConfigParser()
    parser.read(filename)

    info = {}
    if parser.has_section(section):
        items = parser.items(section)
        for item in items:
            info[item[0]] = item[1]
    else:
        raise Exception('{0} not found in the {1} file'.format(section, filename))

    return info


pa_info = read_config('pa')
tg_info = read_config('tg_bot_info')
tg_token, o_user = tg_info['token'], tg_info['user']
vk_info = read_config('vk_bot_info')
vk_token, vk_confirmation, vk_group_id = vk_info['token'], vk_info['confirmation'], int(vk_info['group_id'])

# установка telegram webhook
requests.get(f'https://api.telegram.org/bot{tg_token}/deleteWebhook')
sleep(0.2)
requests.get(f'https://api.telegram.org/bot{tg_token}/setWebhook'
             f'?url={"https://{0}.pythonanywhere.com/{1}_tg".format(pa_info["user"], pa_info["guid"])}'
             f'&allowed_updates=["message"]')

db = sl.connect('records.db')
db.row_factory = sl.Row

# ужас, зато легко прикрутить новую платформу
uctcefr = UltimateClassThatContainsEverythingForReply(db, datetime_format, tz, o_user, tg_token)
ticking_task = subprocess.Popen(['python', f'/home/{pa_info["user"]}/mysite/by_minute_checker_new.py'],
                                executable='python3.8')  # старт тикающего таска, отвечает за отправку сообщений вовремя


# для ответа в телеграме
def send_message_tg(user, m_text, kb):
    # если kb не пуста - создастся json для прикрепления к сообщению
    if kb and kb[0]:
        json_keyboard = json.dumps({'keyboard': kb[0], 'one_time_keyboard': False,
                                    'resize_keyboard': True, 'row_width': 4})
        if len(kb) == 3:
            cursor = db.cursor()
            send_message_tg(user, *uctcefr.interact(user, '/help', 'tg', cursor))
            db.commit()
            cursor.close()
            return
    # если kb пуста - сигнал очистить поле для клавиатуры
    elif kb and not kb[0]:
        json_keyboard = json.dumps({'remove_keyboard': True})
    else:
        json_keyboard = None

    s = requests.get(f'https://api.telegram.org/bot{tg_token}/sendMessage',
                     data=dict(chat_id=user, text=m_text, reply_markup=json_keyboard, parse_mode='HTML')).text
    s = json.loads(s)
    if s.get('ok') is False:
        if s.get('error_code') == 403:  # пользователь заблокировал бота
            clear_all_tasks(user, 'tg')  # чтобы зря не тикали напоминания
        else:
            uctcefr.report_error('отправка тг', str(s))


# форматирует и отправляет ответ для вк
def send_message_vk(user, m_text, kb, r_id):
    # вк не поддерживает какого-либо форматирования текста, так что его надо удалить
    m_text = m_text.replace('/n', '<br>')
    for i in ('i', 'b', 'code'):
        m_text = m_text.replace(f'<{i}>', '')
        m_text = m_text.replace(f'</{i}>', '')

    parameters = f"?v=5.131&random_id={r_id}&access_token={vk_token}&user_id={int(user)}&message={m_text}"

    # генератор клавиатуры
    if kb is not None:
        keyboard = dict(one_time=False, buttons=[])
        if kb[0]:  # если надо её создать
            for i in range(len(kb[0])):
                line = []
                for j in range(len(kb[0][i])):
                    btn = dict(action={"type": "text", "label": kb[0][i][j]}, color=kb[1][i][j]['color'])
                    line.append(btn)
                keyboard['buttons'].append(line)
            if len(kb) == 3:  # какой-то костыль
                keyboard['inline'] = True
            json_keyboard = json.dumps(keyboard).replace('True', 'true')
        else:
            json_keyboard = json.dumps(keyboard)

        parameters += '&keyboard=' + json_keyboard  # прикрепить клавиатуру к сообщению

    s = requests.get("https://api.vk.com/method/messages.send" + parameters).text
    print(s, flush=True)
    s = json.loads(s)
    if s.get('error'):
        if s['error'].get('error_code') == 901:  # пользователь заблокировал бота
            clear_all_tasks(user, 'vk')  # чтобы зря не тикали напоминания
        else:
            uctcefr.report_error('отправка вк', str(s))


# убрать все напоминания пользователя при его пользователя или блокировке им бота
def clear_all_tasks(user, app):
    cursor = db.cursor()
    user = f'{user}_{app}'
    cursor.execute("UPDATE user_status SET part_0_id = NULL, part_1_id = NULL WHERE user = ?", (user,))
    cursor.execute("DELETE FROM actions WHERE user = ?", (user,))
    db.commit()
    cursor.close()


app = Flask(__name__)


@app.route('/{}_restart'.format(pa_info['guid']), methods=["POST"])
def restart_ticking_task():
    global ticking_task

    if ticking_task.poll() is not None:
        ticking_task = subprocess.Popen(['python', f'/home/{pa_info["user"]}/mysite/by_minute_checker_new.py'],
                                        executable='python3.8')

    print("Awakening", flush=True)

    return 'ok', 200


bot = telebot.TeleBot(tg_token, threaded=False)


# обработчик сообщений из телеграма
@app.route('/{}_tg'.format(pa_info['guid']), methods=["POST"])
def webhook_tg():
    stream = request.stream.read().decode("utf-8")
    bot.process_new_updates([telebot.types.Update.de_json(stream)])
    print("Message tg", flush=True)
    return 'ok', 200


# обработчик сообщений из вк
@app.route('/{}_vk'.format(pa_info['guid']), methods=["POST"])
def webhook_vk():
    stream = request.stream.read().decode("utf-8")
    stream = json.loads(stream)

    cursor = db.cursor()

    if stream['group_id'] == vk_group_id:
        if stream['type'] == 'confirmation':
            return vk_confirmation, 200
        elif stream['type'] == 'message_new':
            user = stream['object']['message']['from_id']
            text = stream['object']['message']['text'].replace('\\', '')

            try:
                if 'payload' in stream['object']['message']:
                    if stream['object']['message']['payload'] == {"command": "start"}:
                        text = '/start'

                send_message_vk(user, *uctcefr.interact(user, text, 'vk', cursor), randint(1, 10000000))

            except Exception as error:
                    uctcefr.report_error('обработка входящих сообщений вк', error)
                    send_message_vk(user, 'Что-то пошло не так', None, randint(1, 10000000))
                    print("Message vk error", flush=True)

    db.commit()
    cursor.close()

    print("Message vk", flush=True)
    return 'ok', 200


@bot.message_handler(content_types=['text'])
def interact_text_tg(message):
    cursor = db.cursor()
    try:
        send_message_tg(message.from_user.id, *uctcefr.interact(message.from_user.id, message.text, 'tg', cursor))
    except Exception as error:
        uctcefr.report_error('обработка входящих текстовых сообщений тг', error)
        send_message_tg(message.from_user.id, 'Что-то пошло не так', None)
        print("Message tg error", flush=True)

    db.commit()
    cursor.close()


@bot.message_handler(content_types=["document", "photo", "sticker", "video", "video_note", "location", "contact"])
def interact_media_tg(message):
    cursor = db.cursor()
    try:
        send_message_tg(message.from_user.id, *uctcefr.interact(message.from_user.id, message.caption, 'tg', cursor))
    except Exception as error:
        uctcefr.report_error('обработка входящих медиа сообщений тг', error)
        send_message_tg(message.from_user.id, 'Что-то пошло не так', None)
        print("Message tg error", flush=True)
    db.commit()
    cursor.close()
