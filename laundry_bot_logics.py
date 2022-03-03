from default_keyboards import ReplyKeyboard
from ast import literal_eval
import datetime as dt
import requests
import re
import os


class UltimateClassThatContainsEverythingForReply:
    """
    тут содержатся вообще все функции, которые отвечают за генерацию ответа
    """
    def __init__(self, db, datetime_format, tz, debug_user, debug_bot):
        self.db = db
        self.cursor = None
        self.datetime_format = datetime_format
        self.tz = tz
        self.debug_user = debug_user
        self.debug_bot = debug_bot
        self.is_washing_msg = 'Вещи стираются ' + u'🍏'
        self.is_drying_msg = 'Вещи сушатся ' + u'🍏'
        self.completed_washing_msg = 'Вещи постираны ' + u'🍎'
        self.completed_drying_msg = 'Вещи высушены ' + u'🍎'
        self.parameters_intervals = 'интервалы'
        self.parameters_s_time = 'время тишины'
        self.command_list = ('cancel', 'add_inactive_time', 'delete_inactive_time', 'list_inactive_time',
                             'set_washing_time', 'set_drying_time', 'set_interval_washed',
                             'set_interval_dried', 'help', 'status', 'stop')

    def report_error(self, comment, error):
        text = f'service message\nгде: {comment}\nчто: {error}'
        requests.get(f'https://api.telegram.org/bot{self.debug_bot}/sendMessage?chat_id={self.debug_user}&text={text}')

    def generate_main_reply_kb(self, user):
        self.cursor.execute("SELECT part_0_id, part_1_id FROM user_status WHERE user = ?", (user,))
        part_1_id, part_2_id = self.cursor.fetchall()[0]

        btn_texts, btn_params = [], []
        if part_1_id is None:
            btn_texts.append(self.is_washing_msg)
            btn_params.append({'color': 'primary'})
        else:
            btn_texts.append(self.completed_washing_msg)
            btn_params.append({'color': 'negative'})
        if part_2_id is None:
            btn_texts.append(self.is_drying_msg)
            btn_params.append({'color': 'primary'})
        else:
            btn_texts.append(self.completed_drying_msg)
            btn_params.append({'color': 'negative'})

        # return [[btn_texts, [self.parameters_intervals, self.parameters_s_time]],
        #         [btn_params, [{'color': 'secondary'} for _ in range(2)]]]
        return [[btn_texts, ["настройки"]], [btn_params, [{'color': 'secondary'}]]]

    def convert_inactive_hours_text_to_list(self, text):
        week_planner = [[] for _ in range(7)]

        for row in text:
            row = re.sub('[^A-Za-z0-9:]', ' ', row)
            row = re.sub(r'\s+', ' ', row)
            while ': ' in row or ' :' in row:
                row.replace(' :', ':')
                row.replace(': ', ':')
            try:
                row = row.split()
                t1 = row[-2].split(':')
                t2 = row[-1].split(':')
            except IndexError:
                break

            t1 = [int(i) for i in t1]
            t2 = [int(i) for i in t2]
            dt1, dt2 = dt.time(hour=t1[0], minute=t1[1]), dt.time(hour=t2[0], minute=t2[1])

            if len(row) == 3:  # для одного дня добавили
                if 1 <= int(row[0]) <= 7:
                    if dt1 > dt2:
                        week_planner[int(row[0]) - 1].append(((t1[0], t1[1]), (23, 59)))
                        week_planner[int(row[0]) % 7].append(((0, 0), (t2[0], t2[1])))
                    else:
                        week_planner[int(row[0]) - 1].append(((t1[0], t1[1]), (t2[0], t2[1])))
                else:
                    raise ValueError('WrongFormat')

            elif len(row) == 4:
                if int(row[0]) < 1:
                    row[0] = '1'
                elif int(row[0]) > 7:
                    row[0] = '7'
                if int(row[1]) < 1:
                    row[1] = '1'
                elif int(row[1]) > 7:
                    row[1] = '7'

                days_ow = []

                if int(row[0]) > int(row[1]):
                    days_ow.extend(range(int(row[0]), 8))
                    days_ow.extend(range(1, int(row[1]) + 1))
                else:
                    days_ow.extend(range(int(row[0]), int(row[1]) + 1))

                for i in days_ow:
                    if dt1 > dt2:
                        week_planner[i - 1].append(((t1[0], t1[1]), (23, 59)))
                        week_planner[i % 7].append(((0, 0), (t2[0], t2[1])))
                    else:
                        week_planner[i - 1].append(((t1[0], t1[1]), (t2[0], t2[1])))
            else:
                raise ValueError('WrongFormat')

        return week_planner

    def format_text_from_list(self, rows):
        if len(rows) == 0 or rows[0] == '':
            return None, None

        cnt = 1
        text_to_db, text_to_user = '', '<code>'

        num_size = 1
        for row in rows:
            if row != '\n' and row != '':
                substr = row[:row.find(' ')]
                if len(substr) > 2:
                    num_size = 3
                    break

        for row in rows:
            if row != '\n' and row != '':
                space_pos = row.find(' ')
                dow = row[:space_pos]
                timeline = row[(space_pos + 1):]
                text_to_db += f'{dow} {timeline}\n'
                dow = dow.ljust(num_size)
                text_to_user += f'{str(cnt).zfill(len(str(len(rows))))}. {dow} {timeline}\n'
                cnt += 1

        text_to_user += '</code>'

        return text_to_user, text_to_db

    def parse_inactive_hours_adding(self, input_m):
        input_m = input_m.split('\n')
        human_view = []
        week_planner = [[] for _ in range(7)]

        for row in input_m:
            row = re.sub('[^A-Za-z0-9:]', ' ', row)
            row = re.sub(r'\s+', ' ', row)
            while ': ' in row or ' :' in row:
                row.replace(' :', ':')
                row.replace(': ', ':')

            row = row.split()
            t1 = row[-2].split(':')
            t2 = row[-1].split(':')
            t1 = [int(i) for i in t1]
            t2 = [int(i) for i in t2]
            dt1, dt2 = dt.time(hour=t1[0], minute=t1[1]), dt.time(hour=t2[0], minute=t2[1])

            if len(row) == 3 or row[0] == row[1]:  # для одного дня добавили
                # bot.send_message(debug_user, str(row) + str(len(row)))
                if 1 <= int(row[0]) <= 7:
                    # bot.send_message(debug_user, f'{row[0]} {row[-2]}-{row[-1]}')
                    human_view.append(f'{row[0]} {row[-2]}-{row[-1]}')
                    if dt1 > dt2:
                        week_planner[int(row[0]) - 1].append(((t1[0], t1[1]), (23, 59)))
                        week_planner[int(row[0]) % 7].append(((0, 0), (t2[0], t2[1])))
                    else:
                        week_planner[int(row[0]) - 1].append(((t1[0], t1[1]), (t2[0], t2[1])))
                else:
                    raise ValueError('Wrong format')

            elif len(row) == 4:
                if int(row[0]) < 1:
                    row[0] = '1'
                elif int(row[0]) > 7:
                    row[0] = '7'
                if int(row[1]) < 1:
                    row[1] = '1'
                elif int(row[1]) > 7:
                    row[1] = '7'

                human_view.append(f'{row[0]}-{row[1]} {row[-2]}-{row[-1]}')

                days_ow = []

                if int(row[0]) > int(row[1]):
                    days_ow.extend(range(int(row[0]), 8))
                    days_ow.extend(range(1, int(row[1]) + 1))
                else:
                    days_ow.extend(range(int(row[0]), int(row[1]) + 1))

                for i in days_ow:
                    if dt1 > dt2:
                        week_planner[i - 1].append(((t1[0], t1[1]), (23, 59)))
                        week_planner[i % 7].append(((0, 0), (t2[0], t2[1])))
                    else:
                        week_planner[i - 1].append(((t1[0], t1[1]), (t2[0], t2[1])))

            else:
                raise ValueError('Wrong format')

        return human_view, week_planner

    def timer_set(self, action_type, user):
        now = (dt.datetime.now() + dt.timedelta(hours=self.tz)).strftime(self.datetime_format)

        self.cursor.execute(f"SELECT part_{action_type}_id FROM user_status WHERE user = ?", (user,))
        cur_action_id = self.cursor.fetchone()[0]

        if cur_action_id is not None:
            reply_text = 'Такое напоминание уже установлено'
            reply_kb = self.generate_main_reply_kb(user)
            return reply_text, reply_kb

        self.cursor.execute(f"SELECT default_next_time_minutes_{action_type} FROM user_status WHERE user = ?",
                            (user,))
        awaiting_time = self.cursor.fetchall()[0][0]
        self.cursor.execute(f"SELECT default_interval_{action_type} FROM user_status WHERE user = ?", (user,))
        interval = self.cursor.fetchall()[0][0]
        next_message = dt.datetime.now() + dt.timedelta(hours=self.tz, minutes=awaiting_time)
        next_message = next_message.strftime(self.datetime_format)
        self.cursor.execute("INSERT INTO actions (user, type, last_message, next_message) values (?, ?, ?, ?)",
                            (user, action_type, now, next_message))
        self.cursor.execute("SELECT last_insert_rowid()")
        action_id = self.cursor.fetchall()[0][0]

        self.cursor.execute(f"UPDATE user_status SET part_{action_type}_id = ? WHERE user = ?", (action_id, user))

        if action_type:
            def_command = 'set_drying_time, а интервал /set_interval_dried'
        else:
            def_command = 'set_washing_time, а интервал /set_interval_washed'
        
        reply_text = f"Установлено напоминание\n" \
                     f"Следующее сообщение через {awaiting_time} минут " \
                     f"(если не наступит время тишины), затем интервал в {interval} минут\n\n" \
                     f"<i>Изменить стандартное время ожидания можно командой /{def_command}</i>"
        reply_kb = self.generate_main_reply_kb(user)

        self.db.commit()
        return reply_text, reply_kb
    
    def timer_stop(self, action_type, user):
        self.cursor.execute(f"SELECT part_{action_type}_id FROM user_status WHERE user = ?", (user,))
        action_id = self.cursor.fetchall()[0][0]

        if action_id is None:
            reply_text = 'Это напоминание уже было отменено'
            reply_kb = self.generate_main_reply_kb(user)
            return reply_text, reply_kb

        self.cursor.execute("DELETE FROM actions WHERE id = ?", (action_id,))
        self.cursor.execute(f"UPDATE user_status SET part_{action_type}_id = NULL WHERE user = ?", (user,))

        reply_text = 'Готово'
        reply_kb = self.generate_main_reply_kb(user)

        self.db.commit()
        return reply_text, reply_kb

    def state_0_instructions(self, user, text):
        if text.lower() in self.is_washing_msg.lower():
            reply_text, reply_kb = self.timer_set(0, user)
        elif text.lower() in self.is_drying_msg.lower():
            reply_text, reply_kb = self.timer_set(1, user)
        elif text.lower() in self.completed_washing_msg.lower():
            reply_text, reply_kb = self.timer_stop(0, user)
        elif text.lower() in self.completed_drying_msg.lower():
            reply_text, reply_kb = self.timer_stop(1, user)
        else:
            reply_text, reply_kb = 'a?', None
        return reply_text, reply_kb

    def state_10_instructions(self, user, text, user_state=True):
        r = re.sub('[^0-9]', '', text)

        if r != '':
            new_time = int(r)

            if user_state:
                self.cursor.execute("UPDATE user_status SET default_next_time_minutes_0 = ? WHERE user = ?",
                                    (new_time, user))
            else:
                self.cursor.execute("UPDATE user_status SET default_interval_0 = ? WHERE user = ?", (new_time, user))

            reply_text = 'Готово'
            reply_kb = self.generate_main_reply_kb(user)

            self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))
            self.db.commit()
        else:
            reply_text = 'Неверный формат. Нужно только время в минутах'
            reply_kb = None

        return reply_text, reply_kb

    def state_40_instructions(self, user, text):
        return self.state_10_instructions(user, text, user_state=False)

    def state_15_instructions(self, user, text, user_state=True):
        r = re.sub('[^0-9]', ' ', text)
        r = re.sub(r'\s+', ' ', r)
        r = r.split()

        if not r:
            reply_text = 'Неверный формат. Нужно время в часах и минутах (или только часах)'
            return reply_text, None

        if len(r) <= 2:
            if len(r) == 1:
                new_time = int(r[0]) * 60
            else:
                new_time = int(r[0]) * 60 + int(r[1])

            if user_state:
                self.cursor.execute("UPDATE user_status SET default_next_time_minutes_1 = ? WHERE user = ?",
                                    (new_time, user))
            else:
                self.cursor.execute("UPDATE user_status SET default_interval_1 = ? WHERE user = ?", (new_time, user))

            self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))

            reply_text = 'Готово'
            reply_kb = self.generate_main_reply_kb(user)

        else:
            reply_text = 'Неверный формат. Нужно только время в часах и минутах (или только часах)'
            reply_kb = None

        self.db.commit()
        return reply_text, reply_kb

    def state_45_instructions(self, user, text):
        return self.state_15_instructions(user, text, user_state=False)

    def state_30_instructions(self, user, text):
        input_text = os.linesep.join([s for s in text.splitlines() if s])
        try:
            h_form, l_form = self.parse_inactive_hours_adding(input_text)
        except:
            return 'Что-то не так, попробуйте снова или отмените', None

        # текстовая форма
        self.cursor.execute("SELECT inactive_hours_text FROM user_status WHERE user = ?", (user,))
        old_text = self.cursor.fetchall()[0][0]
        if old_text is None or old_text == '\n':
            text, ttdb = self.format_text_from_list(h_form)
        else:
            text, ttdb = self.format_text_from_list((old_text + '\n' + '\n'.join(h_form)).split('\n'))

        # форма для машины
        self.cursor.execute("SELECT inactive_hours FROM user_status WHERE user = ?", (user,))
        week = self.cursor.fetchall()[0][0]
        if week is None:
            week = [[] for _ in range(7)]
        else:
            week = literal_eval(week)
        for i in range(7):
            week[i].extend(l_form[i])
        week = str(week)
        self.cursor.execute("UPDATE user_status SET inactive_hours = ? WHERE user = ?", (week, user))
        self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))

        ttdb = os.linesep.join([s for s in ttdb.splitlines() if s])

        self.cursor.execute("UPDATE user_status SET inactive_hours_text = ? WHERE user = ?", (ttdb, user))

        reply_text = 'Готово\n\nСейчас список выглядит так:\n' + text
        reply_kb = self.generate_main_reply_kb(user)

        self.db.commit()
        return reply_text, reply_kb

    def state_35_instructions(self, user, text):
        r = re.sub('[^0-9]', ' ', text)
        r = re.sub(r'\s+', ' ', r)
        r = r.split()
        r = [int(i) for i in r]

        self.cursor.execute("SELECT inactive_hours_text FROM user_status WHERE user = ?", (user,))
        try:
            row = self.cursor.fetchall()[0][0]
            rows = [s for s in row.splitlines() if s]

        except AttributeError:
            reply_text = 'Нечего удалять:\n<i>--пусто--</i>'
            reply_kb = self.generate_main_reply_kb(user)
            self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))
            self.db.commit()
            return reply_text, reply_kb

        nothing_changed = True
        ids = list(range(len(rows)))
        for i in r:
            if (i - 1) in ids:
                ids.remove(i - 1)
                nothing_changed = False
        if nothing_changed:
            return 'Укажите строки, которые надо удалить, или отмените', None

        result_message = [rows[i] for i in ids]

        if not len(result_message):
            reply_text = 'Готово\n\nСейчас список выглядит так:\n<i>--пусто--</i>'
            reply_kb = self.generate_main_reply_kb(user)

            week = str([[] for _ in range(7)])
            self.cursor.execute("UPDATE user_status SET inactive_hours = ? WHERE user = ?", (week, user))
            self.cursor.execute("UPDATE user_status SET inactive_hours_text = NULL WHERE user = ?", (user,))
            self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))
            self.db.commit()

            return reply_text, reply_kb

        week = self.convert_inactive_hours_text_to_list(result_message)

        week = str(week)
        self.cursor.execute("UPDATE user_status SET inactive_hours = ? WHERE user = ?", (week, user))

        msg, ttdb = self.format_text_from_list(result_message)
        msg = os.linesep.join([s for s in msg.splitlines() if s])
        ttdb = os.linesep.join([s for s in ttdb.splitlines() if s])
        self.cursor.execute("UPDATE user_status SET inactive_hours_text = ? WHERE user = ?", (ttdb, user))
        self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))

        reply_text = 'Готово\n\nСейчас список выглядит так:\n' + msg
        reply_kb = self.generate_main_reply_kb(user)

        self.db.commit()
        return reply_text, reply_kb

    def state_99_instructions(self, user, text):
        if text.lower() == 'продолжить':
            reply_text = 'Готово. Чтобы начать заново, напишите что-нибудь (/start)'
            reply_kb = None
            self.cursor.execute("DELETE FROM user_status WHERE user = ?", (user,))
            self.cursor.execute("DELETE FROM actions WHERE user = ?", (user,))
        else:
            reply_text = 'Не удалось подтвердить удаление'
            reply_kb = self.generate_main_reply_kb(user)
            self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))

        self.db.commit()
        return reply_text, reply_kb

    def start_command(self, user, source):
        self.cursor.execute("INSERT INTO user_status (user, status, app) values (?, ?, ?)", (user, 0, source))
        self.db.commit()

        reply_text = 'Привет!\nЭтот бот создан для того, чтобы помочь тебе не забыть о вещах в прачечной\n\n' \
                     'Обрати внимание, что тут есть такая штука, как время тишины ' \
                     '(список имеет изначальные значения, его можно посмотреть тут: /list_inactive_time)\n' \
                     'Рекомендуем ознакомиться с разделом /help, содержащим описание команд'
        reply_kb = [[[self.is_washing_msg, self.is_drying_msg], ['настройки']],
                    [[{'color': 'primary'} for _ in range(2)], [{'color': 'secondary'}]]]

        return reply_text, reply_kb

    def cancel_command(self, user):
        reply_text = 'Готово'
        reply_kb = self.generate_main_reply_kb(user)

        self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, reply_kb

    def add_inactive_time_command(self, user):
        reply_text = 'Для добавления промежутков без уведомлений, напишите их ' \
                     'по следующему образцу (одна строка - один промежуток):\n' \
                     '<code>день_недели_1 день_недели_2 время_1 время_2</code>\n' \
                     'Тут <code>день_недели</code> - цифра ' \
                     'от 1 до 7 (от понедельника до воскресенья). ' \
                     'Если необходимо задать правило только для одного дня недели, ' \
                     '<code>день_недели_2</code> можно не писать\n' \
                     '<code>Время</code> в формате <code>Часы:Минуты</code>\n' \
                     'Например, <code>7 5 22:30 5:59</code> (в воскресенье, понедельник, ' \
                     'вторник, ..., пятницу с 22:30 этого дня до 5:59 следующего)\n' \
                     'или <code>1 6 20:00 21:00</code> (понедельник-суббота с 20:00 до 21:00)'
        reply_kb = ReplyKeyboard.cancel.copy()

        self.cursor.execute("UPDATE user_status SET status = 30 WHERE user = ?", (user,))

        return reply_text, reply_kb

    def delete_inactive_time_command(self, user):
        self.cursor.execute("SELECT inactive_hours_text FROM user_status WHERE user = ?", (user,))

        try:
            row = self.cursor.fetchall()[0][0]
            rows = [s for s in row.splitlines() if s]
        except AttributeError:
            self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))
            self.db.commit()
            return 'Нечего удалять:\n<i>--пусто--</i>', None

        text, ttdb = self.format_text_from_list(rows)

        if text is None:
            self.cursor.execute("UPDATE user_status SET status = 0 WHERE user = ?", (user,))
            self.db.commit()
            return 'Нечего удалять:\n<i>--пусто--</i>', None

        reply_text = 'Для удаления свободных от уведомлений промежутков времени, ' \
                     'напишите номер(а) строк, содержащих промежутки для удаления из списка:\n' + text
        reply_kb = ReplyKeyboard.cancel.copy()
        reply_kb[0] = [[str(x) for x in list(range(1, len(rows) + 1 if len(rows) <= 5 else 6))]] + reply_kb[0]
        print(reply_kb[0], flush=True)
        reply_kb[1] = [[{'color': 'secondary'} for _ in range(len(rows) if len(rows) <= 5 else 5)]] + reply_kb[1]

        self.cursor.execute("UPDATE user_status SET status = 35 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, reply_kb

    def list_inactive_time_command(self, user):
        self.cursor.execute("SELECT inactive_hours_text FROM user_status WHERE user = ?", (user,))

        try:
            row = self.cursor.fetchall()[0][0]
            rows = [s for s in row.splitlines() if s]
        except AttributeError:
            return 'Сейчас список выглядит так:\n<i>--пусто--</i>', None

        text, ttdb = self.format_text_from_list(rows)
        reply_text = 'Сейчас список выглядит так:\n' + text

        return reply_text, None

    def set_washing_time_command(self, user):
        self.cursor.execute("SELECT default_next_time_minutes_0 FROM user_status WHERE user = ?", (user,))
        cur = self.cursor.fetchall()[0][0]

        reply_text = f'Стандартное время до первого напоминания о стирке (в минутах)\n' \
                     f'Значение сейчас: {str(cur)} минут\n\n' \
                     f'<i>для активных напоминаний стандартное время останется прежним</i>'
        reply_kb = ReplyKeyboard.washing_time.copy()


        self.cursor.execute("UPDATE user_status SET status = 10 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, reply_kb

    def set_drying_time_command(self, user):
        self.cursor.execute("SELECT default_next_time_minutes_1 FROM user_status WHERE user = ?", (user,))
        cur = self.cursor.fetchall()[0][0]

        reply_text =  f'Стандартное время до первого напоминания о высохших вещах ' \
                      f'(часы и минуты, одинокое число будет принято за количество часов)\n' \
                      f'Значение сейчас: {str(cur)} минут\n\n' \
                      f'<i>для активных напоминаний стандартное время останется прежним</i>'
        reply_kb = ReplyKeyboard.drying_time.copy()

        self.cursor.execute("UPDATE user_status SET status = 15 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, reply_kb


    def set_interval_washed_command(self, user):
        self.cursor.execute("SELECT default_interval_0 FROM user_status WHERE user = ?", (user,))
        cur = self.cursor.fetchall()[0][0]

        reply_text = f'Интервал между напоминаниями о постиранных вещах (в минутах)\n' \
                     f'Значение сейчас: {str(cur)} минут\n\n' \
                     f'<i>новый интервал заработает после следующего напоминания</i>'
        reply_kb = ReplyKeyboard.interval_washed.copy()

        self.cursor.execute("UPDATE user_status SET status = 40 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, reply_kb

    def set_interval_dried_command(self, user):
        self.cursor.execute("SELECT default_interval_1 FROM user_status WHERE user = ?", (user,))
        cur = self.cursor.fetchall()[0][0]

        reply_text = f'Интервал между напоминаниями о высохших вещах (часы и минуты, ' \
                     f'одинокое число будет принято за количество часов)\n' \
                     f'Значение сейчас: {str(cur)} минут\n\n' \
                     f'<i>новый интервал заработает после следующего напоминания</i>'
        reply_kb = ReplyKeyboard.interval_dried.copy()

        self.cursor.execute("UPDATE user_status SET status = 45 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, reply_kb

    def help_command(self, user):
        reply_text = '<b>Описание всех имеющихся команд</b>\n\n' \
                     'Управление значениями времени в напоминаниях:\n' \
                     '-- /set_washing_time - время, отводимое на стирку (т. е. время до первого напоминания)\n' \
                     '-- /set_drying_time - время, отводимое на сушку вещей (т. е. время до первого напоминания)\n' \
                     '-- /set_interval_washed - время между напоминаниями о ' \
                     'постиравшихся вещах (т. е. после первого напоминания)\n' \
                     '-- /set_interval_dried - время между напоминаниями о ' \
                     'вещах в сушилке (т. е. после первого напоминания)\n' \
                     '\nУправление промежутками времени, в которые не будут приходить напоминания:\n' \
                     '-- /list_inactive_time - посмотреть список\n' \
                     '-- /add_inactive_time - добавить\n' \
                     '-- /delete_inactive_time - удалить некоторые\n' \
                     '\nПрочее:\n' \
                     '-- /stop - сбросить всё'

        if user.endswith('vk'):
            reply_text += '\n\n(P.S. в вк все эти команды можно найти, если тыкнуть кнопку "настройки")'

        return reply_text, None

    def contact_us_command(self, user):
        reply_text = 'Следующее сообщение получит человек'
        reply_kb = ReplyKeyboard.cancel.copy()

        self.cursor.execute("UPDATE user_status SET status = 20 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, reply_kb

    def status_command(self, user):
        self.cursor.execute("SELECT last_check FROM info")
        last_check = self.cursor.fetchone()[0]

        total_users = vk_users = tg_users = last_n_days_vk = last_n_days_tg = 0

        self.cursor.execute("SELECT user, last_used FROM user_status")
        for user in self.cursor.fetchall():
            total_users += 1
            user_id, app = user[0].split('_')

            if app == 'vk':
                vk_users += 1
            elif app == 'tg':
                tg_users += 1
                
            if user[1]:
                last_used = dt.datetime.strptime(user[1], self.datetime_format)
                if last_used > dt.datetime.now() - dt.timedelta(days=20):
                    if app == 'vk':
                        last_n_days_vk += 1
                    elif app == 'tg':
                        last_n_days_tg += 1

        self.cursor.execute("SELECT Count() FROM actions")
        actions_count = self.cursor.fetchone()[0]

        reply_text = f'Последняя проверка: {last_check}\n' \
                     f'Активных напоминаний: {actions_count}\n' \
                     f'Vk / tg / total: {vk_users} / {tg_users} / {vk_users + tg_users}\n' \
                     f'Из них за последние 20 дней: ' \
                     f'{last_n_days_vk} / {last_n_days_tg} / {last_n_days_vk + last_n_days_tg}'

        return reply_text, None

    def stop_command(self, user):
        reply_text = 'При удалении потеряются все настройки. Для подтверждения напишите "продолжить" без кавычек'

        self.cursor.execute("UPDATE user_status SET status = 99 WHERE user = ?", (user,))
        self.db.commit()

        return reply_text, [[], []]

    def interact(self, user, message_text, source, cursor):
        user = str(user) + '_' + source
        self.cursor = cursor
        try:
            user_state = self.cursor.execute("SELECT status FROM user_status WHERE user = ?", (user,)).fetchone()[0]
        except:
            user_state = None

        self.cursor.execute("UPDATE user_status SET last_used = ? WHERE user = ?",
                            (dt.datetime.now().strftime(self.datetime_format), user))
        self.db.commit()

        reply_text, reply_kb = 'а?', None

        # /start
        if user_state is None:
            return self.start_command(user, source)
        elif message_text.startswith('/start'):
            reply_text = 'Уже работаем'
            return reply_text, None

        # /commands
        if message_text.startswith('/'):
            command = message_text[1:] if message_text.find(' ') == -1 else message_text[1:message_text.find(' ')]
            if command in self.command_list:
                try:
                    reply_text, reply_kb = eval(f'self.{command}_command(user)')
                except Exception as error:
                    self.report_error(f'выполнение {command}', error)
            else:
                reply_text = 'Неправильная команда. Нужна /help?'

        else:
            tmp = message_text.lower()
            tmp = tmp.replace(' ', '')
            if tmp in ('отменитьвыбор', 'отменить', 'отмена', 'cancel', 'stopit', 'стоп', 'отказ', 'достал'):
                reply_text, reply_kb = self.cancel_command(user)
            elif tmp == self.parameters_intervals.replace(' ', ''):
                reply_text = 'настройки интервалов для напоминаний'
                reply_kb = ReplyKeyboard.intervals_inline.copy()
            elif tmp == self.parameters_s_time.replace(' ', ''):
                reply_text = 'настройки времени тишины'
                reply_kb = ReplyKeyboard.inactive_time_inline.copy()
            elif tmp in ('настройки', 'параметры', 'settings', 'parameters'):
                reply_text = 'категория'
                reply_kb = ReplyKeyboard.main_settings_inline.copy()
            else:
                try:
                    reply_text, reply_kb = eval(f'self.state_{user_state}_instructions(user, message_text)')
                except Exception as error:
                    self.report_error(f'инструкция {user_state}', error)

        return reply_text, reply_kb
