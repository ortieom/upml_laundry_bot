# -*- coding: utf-8 -*-
from configparser import ConfigParser
from random import randint
from ast import literal_eval
from time import sleep
import datetime as dt
import sqlite3 as sl
import requests
import json
import sys


"""
тот самый тикающий таск
этот скрипт каждую минуту проверяет, не пора ли отправить напоминание пользователю
"""


# text to send by schedule for different types
messages = {'0_1': "Время развесить постиранное",
            '1_1': "Время забрать вещи из сушилки"}

datetime_format = '%d.%m.%Y %H:%M'
tz = dt.timedelta(hours=5)  # (UTC+5), в системе по UTC


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


bot_info = read_config('tg_bot_info')
secret_token_to_b = bot_info['token']
debug_user = bot_info['user']
vk_info = read_config('vk_bot_info')
vk_token = vk_info['token']


def send_message_tg(user, text, db):
    s = requests.get(f'https://api.telegram.org/bot{secret_token_to_b}/sendMessage',
                     data=dict(chat_id=user, text=text, parse_mode='HTML')).text
    s = json.loads(s)
    if s.get('ok') is False:
        if s.get('error_code') == 403:
            clear_all_tasks(user, 'tg', db)
        else:
            send_message_tg(debug_user, 'отправка тг', db)


def send_message_vk(user, m_text, db):
    parameters = f"?v=5.131&random_id={randint(1, 1000000)}&access_token={vk_token}&user_id={int(user)}&message={m_text}"
    s = requests.get("https://api.vk.com/method/messages.send" + parameters).text
    s = json.loads(s)
    if s.get('error'):
        if s['error'].get('error_code') == 901:
            clear_all_tasks(user, 'vk', db)
        else:
            send_message_tg(debug_user, 'отправка вк', db)
    # print(s.text + ' as reply for parameters: ' + parameters, flush=True)


def clear_all_tasks(user, app, db):
    cursor = db.cursor()
    user = f'{user}_{app}'
    cursor.execute("UPDATE user_status SET part_0_id = NULL, part_1_id = NULL WHERE user = ?", (user,))
    cursor.execute("DELETE FROM actions WHERE user = ?", (user,))
    db.commit()
    cursor.close()


def get_minutes(a_type, user, db_cursor):
    db_cursor.execute(f"SELECT default_interval_{a_type} FROM user_status WHERE user = ?", (user,))
    awaiting_time = db_cursor.fetchall()[0][0]

    return awaiting_time


def datetime_range(start, end, delta):
    current = start
    while current < end:
        yield current
        current += delta


def status(cursor):
    cursor.execute("SELECT last_check FROM info")
    last_check = cursor.fetchone()[0]

    total_users = vk_users = tg_users = last_n_days_vk = last_n_days_tg = 0

    cursor.execute("SELECT user, last_used FROM user_status")
    for user in cursor.fetchall():
        total_users += 1
        user_id, app = user[0].split('_')

        if app == 'vk':
            vk_users += 1
        elif app == 'tg':
            tg_users += 1

        if user[1]:
            last_used = dt.datetime.strptime(user[1], datetime_format)
            if last_used > dt.datetime.now() - dt.timedelta(days=20):
                if app == 'vk':
                    last_n_days_vk += 1
                elif app == 'tg':
                    last_n_days_tg += 1

    cursor.execute("SELECT Count() FROM actions")
    actions_count = cursor.fetchone()[0]

    reply_text = f'Последняя проверка: {last_check}\n' \
                 f'Активных напоминаний: {actions_count}\n' \
                 f'Vk / tg / total: {vk_users} / {tg_users} / {vk_users + tg_users}\n' \
                 f'Из них за последние 20 дней: ' \
                 f'{last_n_days_vk} / {last_n_days_tg} / {last_n_days_vk + last_n_days_tg}'

    return reply_text


def main(now_dt, is_first):
    # db = sl.connect('records.db')
    db = sl.connect('/home/upmlLaundryBot/mysite/records.db')
    cursor = db.cursor()

    # во сколько была последняя проверка (на случай падений)
    cursor.execute("SELECT last_check FROM info")
    last_check = cursor.fetchone()[0]

    # отметка текущей проверки
    cursor.execute("UPDATE info SET last_check = ?", (now_dt.strftime(datetime_format),))

    if last_check is None:  # первый запуск
        return 0

    # записывает время в виде строк, которое будет использоваться в запросах (sqlite не поддерживает работу со временем)
    # сломается, если бот давно простаивает. не критично
    minutes = [x.strftime(datetime_format) for x in
               datetime_range(dt.datetime.strptime(last_check, datetime_format) + dt.timedelta(minutes=1),
                              now_dt, dt.timedelta(minutes=1))]

    if len(minutes) == 0 and not is_first:
        # такое поведение характерно нескольким одновременно запущенным тикающим таскам
        print('Duplicated subprocess killed', flush=True)
        sys.exit()

    elif len(minutes) > 1:  # увведомить о простое
        if len(minutes) > 5:
            send_message_tg(debug_user, str(minutes) + '\n' + status(cursor), db)
        print(f'downtime: {str(minutes)}', flush=True)

    # print(str(minutes), flush=True)
    # print(len(minutes), flush=True)

    reminders_queue = []  # очередь сообщений для отправки
    for minute in minutes:
        # print(minute + ' requested', flush=True)
        cursor.execute('SELECT * FROM actions WHERE next_message = ?', (minute,))
        reminders_queue.extend(cursor.fetchall())

    for reminder in reminders_queue:  # рассылка сообщений и планирование следующих
        l_m = reminder[3]
        cnt = reminder[5]

        print(reminder[1], flush=True)
        user_id, app = reminder[1].split('_')

        # проверка на часы неактивности
        send_now = True  # отправить ли сообщение сейчас или отложить
        cursor.execute('SELECT inactive_hours FROM user_status WHERE user = ?', (reminder[1],))
        inactive_hours = cursor.fetchall()[0][0]
        try:
            inactive_hours = literal_eval(inactive_hours)
        except ValueError:
            inactive_hours = [[] for _ in range(7)]
        dow = now_dt.weekday()
        for pair in inactive_hours[dow]:
            h1, m1 = pair[0]
            h2, m2 = pair[1]
            t1 = dt.time(hour=int(h1), minute=int(m1))
            t2 = dt.time(hour=int(h2), minute=int(m2), second=59)
            if t1 <= now_dt.time() <= t2:
                send_now = False

        if send_now:
            l_m = reminder[4]
            cnt += 1

            msg = messages[str(reminder[2]) + '_1'] + f' ({cnt})'  # текст напоминалки
            if app == 'tg':  # отправка
                send_message_tg(user_id, msg, db)
            else:
                send_message_vk(user_id, msg, db)

            # через сколько минут будет следующее сообщение
            delay_minutes = get_minutes(reminder[2], reminder[1], cursor)
            next_message = (now_dt + dt.timedelta(minutes=delay_minutes)).strftime(datetime_format)

        else:  # inactive hours
            next_message = (now_dt + dt.timedelta(minutes=1)).strftime(datetime_format)

        cursor.execute('UPDATE actions SET last_message = ?, next_message = ?, cnt = ? WHERE id = ?',
                       (l_m, next_message, cnt, reminder[0]))

    db.commit()
    cursor.close()
    db.close()

    return 0


if __name__ == '__main__':
    first_launch = True
    now = dt.datetime.now() + tz

    while True:
        try:
            main(now, first_launch)
        except Exception as Error:
            send_message_tg(debug_user, 'Ошибка в тикающем таске:\n' + str(Error) + '\n\n' + str(now), None)

        first_launch = False

        sleep(61 - dt.datetime.now().second)
        now += dt.timedelta(minutes=1)
