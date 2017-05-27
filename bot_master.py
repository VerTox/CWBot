# coding=utf-8
from pytg.sender import Sender
from pytg.receiver import Receiver
from pytg.utils import coroutine
from collections import deque
from time import time, sleep, strftime, gmtime
from getopt import getopt
from datetime import datetime
import sys
import re
import _thread
import random
import pytz
import configparser

# username игрового бота
bot_username = 'ChatWarsBot'

# ваш username или username человека, который может отправлять запросы этому скрипту
admin_username = ''

# username бота и/или человека, которые будут отправлять приказы
order_usernames = ''

# имя замка
castle_name = ''

captcha_bot = 'ChatWarsCaptchaBot'

# путь к сокет файлу
socket_path = ''

# хост чтоб слушать telegram-cli
host = 'localhost'

# порт по которому слушать
port = 1338

# включить прокачку при левелапе
lvl_up = 'lvl_off'

# имя группы
group_name = ''

config = configparser.ConfigParser()

# user_id бота, используется для поиска конфига
bot_user_id = ''

opts, args = getopt(sys.argv[1:], 'a:o:c:s:h:p:g:b:l:n', ['admin=', 'order=', 'castle=', 'socket=', 'host=', 'port=',
                                                          'gold=', 'lvlup=', 'group_name='])

for opt, arg in opts:
    if opt in ('-a', '--admin'):
        admin_username = arg
    elif opt in ('-o', '--order'):
        order_usernames = arg.split(',')
    elif opt in ('-c', '--castle'):
        castle_name = arg
    elif opt in ('-s', '--socket'):
        socket_path = arg
    elif opt in ('-h', '--host'):
        host = arg
    elif opt in ('-p', '--port'):
        port = int(arg)
    elif opt in ('-g', '--gold'):
        gold_to_left = int(arg)
    elif opt in ('-l', '--lvlup'):
        lvl_up = arg
    elif opt in ('-n', '--group_name'):
        group_name = arg



orders = {
    'red': '🇮🇲',
    'black': '🇬🇵',
    'white': '🇨🇾',
    'yellow': '🇻🇦',
    'blue': '🇪🇺',
    'mint': '🇲🇴',
    'twilight': '🇰🇮',
    'lesnoi_fort': '🌲Лесной форт',
    'les': '🌲Лес',
    'gorni_fort': '⛰Горный форт',
    'gora': '⛰',
    'cover': '🛡 Защита',
    'attack': '⚔ Атака',
    'cover_symbol': '🛡',
    'hero': '🏅Герой',
    'corovan': '/go',
    'peshera': '🕸Пещера',
    'quests': '🗺 Квесты',
    'castle_menu': '🏰Замок',
    'lavka': '🏚Лавка',
    'snaraga': 'Снаряжение',
    'shlem': 'Шлем',
    'sell': 'Скупка предметов',
    'lvl_def': '+1 🛡Защита',
    'lvl_atk': '+1 ⚔️Атака',
    'lvl_off': 'Выключен'
}

captcha_answers = {
    # блядь, кольцов, ну и хуйню же ты придумал
    'watermelon_n_cherry': '🍉🍒',
    'bread_n_cheese': '🍞🧀',
    'cheese': '🧀',
    'pizza': '🍕',
    'hotdog': '🌭',
    'eggplant_n_carrot': '🍆🥕',
    'dog': '🐕',
    'horse': '🐎',
    'goat': '🐐',
    'cat': '🐈',
    'pig': '🐖',
    'squirrel': '🐿'
}

arena_cover = ['🛡головы', '🛡корпуса', '🛡ног']
arena_attack = ['🗡в голову', '🗡по корпусу', '🗡по ногам']
# поменять blue на red, black, white, yellow в зависимости от вашего замка
castle = orders[castle_name]
# текущий приказ на атаку/защиту, по умолчанию всегда защита, трогать не нужно
current_order = {'time': 0, 'order': castle}
# задаем получателя ответов бота: админ или группа
if group_name == '':
    pref = '@'
    msg_receiver = admin_username
else:
    pref = ''
    msg_receiver = group_name

sender = Sender(sock=socket_path) if socket_path else Sender(host=host,port=port)
action_list = deque([])
log_list = deque([], maxlen=30)
lt_arena = 0
lt_info = 0
get_info_diff = 360
hero_message_id = 0
last_captcha_id = 0
gold_to_left = 0
endurance = 0
gold = 0
hero_state = 'relax'

bot_enabled = True
arena_enabled = True
les_enabled = True
peshera_enabled = False
corovan_enabled = True
order_enabled = True
auto_def_enabled = True
donate_enabled = False
quest_fight_enabled = True
building_enabled = True
building_paused = False
tl_build_try = 0
building_target = '/build_hq'

arena_running = False
arena_delay = False
arena_delay_day = -1
tz = pytz.timezone('Europe/Moscow')

@coroutine
def work_with_message(receiver):
    global bot_user_id
    global castle_name
    while True:
        msg = (yield)
        try:
            if msg['event'] == 'message' and 'text' in msg and msg['peer'] is not None:
                if bot_user_id == '' and msg['sender']['username'] == bot_username:
                    bot_user_id = msg['receiver']['peer_id']
                    log('user_id найден: {0}'.format(bot_user_id))
                    config.read('./bot_cfg/' + str(bot_user_id) + '.cfg')
                    if config.has_section(str(bot_user_id)):
                        log('Конфиг найден')
                        read_config()
                        log('Конфиг загружен')
                    else:
                        log('Конфиг не найден')
                        write_config()
                        log('Новый конфиг создан')
                # Если твинкоботы просят помощи, форвардим в черный замок
                if group_name != '' and castle_name == 'black':
                    if msg['peer']['name'] == group_name and msg['text'].find('/fight') != -1:
                        fwd("@", 'blackcastlebot', msg['id'])
                # Проверяем наличие юзернейма, чтобы не вываливался Exception
                if 'username' in msg['sender']:
                    log(msg['sender']['username'])
                    parse_text(msg['text'], msg['sender']['username'], msg['id'])
        except Exception as err:
            log('Ошибка coroutine: {0}'.format(err))


def queue_worker():
    global get_info_diff
    global arena_delay
    global arena_delay_day
    global tz
    global lt_info
    global hero_state
    global auto_def_enabled
    global donate_enabled
    global gold
    # гребаная магия
    print(sender.contacts_search(bot_username))
    print(sender.contacts_search(captcha_bot))
    sleep(3)
    while True:
        try:
            if time() - lt_info > get_info_diff:
                if arena_delay and arena_delay_day != datetime.now(tz).day:
                    arena_delay = False
                lt_info = time()
                get_info_diff = random.randint(2100, 2400)
                if bot_enabled and hero_state == 'relax':
                    send_msg('@', bot_username, orders['hero'])
                continue

            if len(action_list):
                log('Отправляем ' + action_list[0])
                send_msg('@', bot_username, action_list.popleft())
            if hero_state == 'attack_ready' or hero_state == 'defence_ready':
                if after_battle_time():
                    hero_state = 'relax'
                    send_msg('@', bot_username, orders['hero'])
            if hero_state == 'relax' and auto_def_enabled and pre_battle_time():
                if donate_enabled:
                    log('Донат {0} золота в казну замка'.format(gold - gold_to_left))
                    action_list.append('/donate {0}'.format(gold - gold_to_left))
                update_order(castle)
            sleep_time = random.randint(2, 5)
            sleep(sleep_time)
        except Exception as err:
            log('Ошибка очереди: {0}'.format(err))


def read_config():
    global config
    global bot_user_id
    global bot_enabled
    global arena_enabled
    global les_enabled
    global peshera_enabled
    global corovan_enabled
    global auto_def_enabled
    global donate_enabled
    global lvl_up
    global quest_fight_enabled
    global building_target
    global building_enabled
    section=str(bot_user_id)
    bot_enabled=config.getboolean(section, 'bot_enabled')
    arena_enabled=config.getboolean(section, 'arena_enabled')
    les_enabled=config.getboolean(section, 'les_enabled')
    peshera_enabled=config.getboolean(section, 'peshera_enabled')
    corovan_enabled=config.getboolean(section, 'corovan_enabled')
    auto_def_enabled=config.getboolean(section, 'auto_def_enabled')
    donate_enabled=config.getboolean(section, 'donate_enabled')
    building_enabled = config.getboolean(section, 'building_enabled')
    building_target = config.get(section, 'building_target')
    lvl_up=config.get(section, 'lvl_up')
    quest_fight_enabled=config.getboolean(section, 'quest_fight_enabled')

def write_config():
    global config
    global bot_user_id
    global bot_enabled
    global arena_enabled
    global les_enabled
    global peshera_enabled
    global corovan_enabled
    global auto_def_enabled
    global donate_enabled
    global lvl_up
    global quest_fight_enabled
    global building_target
    global building_enabled
    section = str(bot_user_id)
    if config.has_section(section):
        config.remove_section(section)
    config.add_section(section)
    config.set(section, 'bot_enabled', str(bot_enabled))
    config.set(section, 'arena_enabled', str(arena_enabled))
    config.set(section, 'les_enabled', str(les_enabled))
    config.set(section, 'peshera_enabled', str(peshera_enabled))
    config.set(section, 'corovan_enabled', str(corovan_enabled))
    config.set(section, 'auto_def_enabled', str(auto_def_enabled))
    config.set(section, 'donate_enabled', str(donate_enabled))
    config.set(section, 'lvl_up', str(lvl_up))
    config.set(section, 'building_enabled', str(building_enabled))
    config.set(section, 'building_target', str(building_target))
    config.set(section, 'quest_fight_enabled', str(quest_fight_enabled))
    with open('./bot_cfg/' + str(bot_user_id) + '.cfg', 'w+') as configfile:
        config.write(configfile)

def parse_text(text, username, message_id):
    global lt_arena
    global lt_info
    global hero_message_id
    global bot_enabled
    global arena_enabled
    global les_enabled
    global peshera_enabled
    global corovan_enabled
    global order_enabled
    global auto_def_enabled
    global donate_enabled
    global last_captcha_id
    global arena_delay
    global arena_delay_day
    global tz
    global arena_running
    global lvl_up
    global pref
    global msg_receiver
    global quest_fight_enabled
    global endurance
    global building_enabled
    global building_paused
    global lt_build_try
    global building_target
    global hero_state
    global gold
    global action_list
    if bot_enabled and username == bot_username:
        log('Получили сообщение от бота. Проверяем условия')

        if text.find('🌟Поздравляем! Новый уровень!') != -1 and lvl_up != 'lvl_off':
            log('получили уровень - {0}'.format(orders[lvl_up]))
            action_list.append('/level_up')
            action_list.append(orders[lvl_up])

        elif "На выходе из замка охрана никого не пропускает" in text:
            # send_msg('@', admin_username, "Командир, у нас проблемы с капчой! #captcha " + '|'.join(captcha_answers.keys()))
            # fwd('@', admin_username, message_id)
            action_list.clear()
            bot_enabled = False
            last_captcha_id = message_id
            fwd('@', captcha_bot, message_id)

        elif 'Не умничай!' in text or 'Ты долго думал, аж вспотел от напряжения' in text:
            send_msg('@', admin_username, "Командир, у нас проблемы с капчой! #captcha " + '|'.join(captcha_answers.keys()))
            bot_enabled = False
            if last_captcha_id != 0:
                fwd('@', admin_username, message_id)
            else:
                send_msg('@', admin_username, 'Капча не найдена?')

        elif 'На сегодня ты уже своё отвоевал. Приходи завтра.' in text:
            arena_delay = True
            arena_delay_day = datetime.now(tz).day
            log("Отдыхаем денек от арены")
            arena_running = False

        elif corovan_enabled and text.find(' /go') != -1:
            action_list.append(orders['corovan'])

        elif text.find('Ты отправился искать приключения в лес.') != -1:
            hero_state = 'forest'
            endurance -= 1

        elif text.find('Ты отправился искать приключения в пещеру.') != -1:
            hero_state = 'peshera'
            endurance -= 2

        elif text.find('Ты встал на защиту КОРОВАНА.') != -1:
            hero_state = 'caravan'

        elif text.find('Ты приготовился к защите') != -1:
            hero_state = 'defence_ready'

        elif text.find('Ты приготовился к атаке') != -1:
            hero_state = 'attack_ready'

        elif text.find('Ты пошел строить:') != -1:
            hero_state = 'building'

        elif text.find('Ищем соперника.') != -1:
            hero_state = 'arena'
            arena_running = True
            log('Пришли на арену, ждем соперника')

        elif text.find('Слишком мало единиц выносливости.') != -1:
            endurance = 0
            hero_state = 'relax'

        elif text.find('Ты задержал') != -1 or text.find('Ты упустил') != -1 or text.find('Ты пытался остановить') != -1 or text.find('Слишком поздно, событие не актуально.') != -1 or text.find('Ветер завывает') != -1 or text.find('Ты заработал:') != -1 or forest_end(text):
            hero_state = 'relax'

        elif text.find('Битва семи замков через') != -1:
            hero_message_id = message_id
            lt_info = time()
            try_parse_status(text)
            gold = int(re.search('💰([0-9]+)', text).group(1))
            endurance = int(re.search('Выносливость: ([0-9]+)', text).group(1))
            log('Золото: {0}, выносливость: {1}'.format(gold, endurance))

        elif text.find('В казне недостаточно ресурсов для строительства') != -1:
            log('Нет денег в казне')
            building_paused = True
            lt_build_try = time()

        elif arena_enabled and text.find('выбери точку атаки и точку защиты') != -1:
            arena_running = True #на случай, если арена запущена руками
            lt_arena = time()
            attack_chosen = arena_attack[random.randint(0, 2)]
            cover_chosen = arena_cover[random.randint(0, 2)]
            log('Атака: {0}, Защита: {1}'.format(attack_chosen, cover_chosen))
            action_list.append(attack_chosen)
            action_list.append(cover_chosen)

        elif text.find('Победил воин') != -1 or text.find('Ничья') != -1:
            log('Выключаем флаг - арена закончилась')
            arena_running = False
            fwd('@', 'blackcastlebot', message_id)

        elif building_enabled and text.find('Ты вернулся со стройки:') != -1 and endurance == 0:
            hero_state = 'relax'
            fwd('@', 'blackcastlebot', message_id)

        if quest_fight_enabled and text.find('/fight') != -1:
            c = re.search('(\/fight.*)', text).group(1)
            action_list.append(c)
            # заготовка для твинков
            # fwd(pref, msg_receiver, message_id)
            fwd('@', 'blackcastlebot', message_id)

        if hero_state == 'relax':
            if endurance != 0:
                log('Выносливость осталась, идем на квесты')
                go_to_quest()
            elif arena_available():
                log('Можно идти на арену')
                go_to_arena()
            elif building_available():
                log('Можно идти на стройку')
                go_to_building()
            else:
                log('В данный момент нечем заняться')

        if hero_state == 'relax' and arena_running:
            arena_running = False

        log(hero_state)

    elif username == 'ChatWarsCaptchaBot':
        if len(text) <= 4 and text in captcha_answers.values():
            sleep(3)
            action_list.append(text)
            bot_enabled = True

    # elif username == '' and text.find('/fight') != -1:
    #        c = re.search('(\/fight.*)', text).group(1))
    #        fwd("@", msg_receiver, message_id)

    else:
        if username == admin_username:
            if text == '#help':
                send_msg(pref, msg_receiver, '\n'.join([
                    '#enable_bot - Включить бота',
                    '#disable_bot - Выключить бота',
                    '#enable_arena - Включить арену',
                    '#disable_arena - Выключить арену',
                    '#enable_les - Включить лес',
                    '#disable_les - Выключить лес',
                    '#enable_peshera - Включить пещеры',
                    '#disable_peshera - Выключить пещеры',
                    '#enable_corovan - Включить корован',
                    '#disable_corovan - Выключить корован',
                    '#enable_order - Включить приказы',
                    '#disable_order - Выключить приказы',
                    '#enable_auto_def - Включить авто деф',
                    '#disable_auto_def - Выключить авто деф',
                    '#enable_donate - Включить донат',
                    '#disable_donate - Выключить донат',
                    '#enable_quest_fight - Включить битву во время квестов',
                    '#disable_quest_fight - Выключить битву во время квестов',
                    "#lvl_atk - качать атаку",
                    "#lvl_def - качать защиту",
                    "#lvl_off - ничего не качать",
                    '#status - Получить статус',
                    '#hero - Получить информацию о герое',
                    '#push_order - Добавить приказ ({0})'.format(','.join(orders)),
                    '#order - Дебаг, последняя команда защиты/атаки замка',
                    '#log - Дебаг, последние 30 сообщений из лога',
                    '#time - Дебаг, текущее время',
                    '#lt_arena - Дебаг, последняя битва на арене',
                    '#get_info_diff - Дебаг, последняя разница между запросами информации о герое',
                    '#ping - Дебаг, проверить жив ли бот',
                ]))

            # Вкл/выкл бота
            elif text == '#enable_bot':
                bot_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Бот успешно включен')
            elif text == '#disable_bot':
                bot_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Бот успешно выключен')

            # Вкл/выкл арены
            elif text == '#enable_arena':
                arena_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Арена успешно включена')
            elif text == '#disable_arena':
                arena_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Арена успешно выключена')

            # Вкл/выкл леса
            elif text == '#enable_les':
                les_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Лес успешно включен')
            elif text == '#disable_les':
                les_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Лес успешно выключен')

            # Вкл/выкл пещеры
            elif text == '#enable_peshera':
                peshera_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Пещеры успешно включены')
            elif text == '#disable_peshera':
                peshera_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Пещеры успешно выключены')

            # Вкл/выкл корована
            elif text == '#enable_corovan':
                corovan_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Корованы успешно включены')
            elif text == '#disable_corovan':
                corovan_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Корованы успешно выключены')

            # Вкл/выкл команд
            elif text == '#enable_order':
                order_enabled = True
                send_msg(pref, msg_receiver, 'Приказы успешно включены')
            elif text == '#disable_order':
                order_enabled = False
                send_msg(pref, msg_receiver, 'Приказы успешно выключены')

            # Вкл/выкл авто деф
            elif text == '#enable_auto_def':
                auto_def_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Авто деф успешно включен')
            elif text == '#disable_auto_def':
                auto_def_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Авто деф успешно выключен')

            # Вкл/выкл авто донат
            elif text == '#enable_donate':
                donate_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Донат успешно включен')
            elif text == '#disable_donate':
                donate_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Донат успешно выключен')

            # Вкл/выкл битву по время квеста
            elif text == '#enable_quest_fight':
                quest_fight_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Битва включена')
            elif text == '#disable_quest_fight':
                quest_fight_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Битва отключена')

            elif text == '#enable_building':
                building_enabled = True
                write_config()
                send_msg(pref, msg_receiver, 'Строительство включено')
            elif text == '#disable_building':
                building_enabled = False
                write_config()
                send_msg(pref, msg_receiver, 'Строительство выключено')

            # что качать при левелапе
            elif text == '#lvl_atk':
                lvl_up = 'lvl_atk'
                write_config()
                send_msg(pref, msg_receiver, 'Качаем атаку')
            elif text == '#lvl_def':
                lvl_up = 'lvl_def'
                write_config()
                send_msg(pref, msg_receiver, 'Качаем защиту')
            elif text == '#lvl_off':
                lvl_up = 'lvl_off'
                write_config()
                send_msg(pref, msg_receiver, 'Не качаем ничего')

            # Получить статус
            elif text == '#status':
                send_msg(pref, msg_receiver, '\n'.join([
                    '🤖Бот включен: {0}',
                    '📯Арена включена: {1}',
                    '🔎Сейчас на арене: {2}',
                    '🌲Лес включен: {3}',
                    '🕸Пещеры включены: {4}',
                    '🐫Корованы включены: {5}',
                    '🇪🇺Приказы включены: {6}',
                    '🛡Авто деф включен: {7}',
                    '💰Донат включен: {8}',
                    '🌟Левелап: {9}',
                ]).format(bot_enabled, arena_enabled, arena_running, les_enabled, peshera_enabled, corovan_enabled, order_enabled,
                          auto_def_enabled, donate_enabled, orders[lvl_up]))

            # Информация о герое
            elif text == '#hero':
                if hero_message_id == 0:
                    send_msg(pref, msg_receiver, 'Информация о герое пока еще недоступна')
                else:
                    fwd(pref, msg_receiver, hero_message_id)

            # Получить лог
            elif text == '#log':
                send_msg(pref, msg_receiver, '\n'.join(log_list))
                log_list.clear()

            elif text == '#lt_arena':
                send_msg(pref, msg_receiver, str(lt_arena))

            elif text == '#order':
                text_date = datetime.fromtimestamp(current_order['time']).strftime('%Y-%m-%d %H:%M:%S')
                send_msg(pref, msg_receiver, current_order['order'] + ' ' + text_date)

            elif text == '#time':
                text_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                send_msg(pref, msg_receiver, text_date)

            elif text == '#ping':
                send_msg(pref, msg_receiver, '#pong')

            elif text == '#get_info_diff':
                send_msg(pref, msg_receiver, str(get_info_diff))

            elif text == '#stock':
                action_list.append('/stock')

            elif text.startswith('#build_target'):
                command = text.split(' ')[1]
                building_target = command
                send_msg(pref, msg_receiver, 'Новая цель строительства: "' + command + '" установлена')

            elif text.startswith('#push_order'):
                command = text.split(' ')[1]
                if command in orders:
                    update_order(orders[command])
                    send_msg(pref, msg_receiver, 'Команда ' + command + ' применена')
                else:
                    send_msg(pref, msg_receiver, 'Команда ' + command + ' не распознана')

            elif text.startswith('#captcha'):
                command = text.split(' ')[1]
                if command in captcha_answers:
                    action_list.append(captcha_answers[command])
                    bot_enabled = True
                    send_msg('@', admin_username, 'Команда ' + command + ' применена')
                else:
                    send_msg('@', admin_username, 'Команда ' + command + ' не распознана')


def try_parse_status(text):
    global hero_state
    if re.search('Отдых', text):
        hero_state = 'relax'
    elif re.search('В лесу. Вернешься через', text):
        hero_state = 'forest'
    elif re.search('На арене', text):
        hero_state = 'arena'
    elif re.search('В пещере', text):
        hero_state = 'cave'
    elif re.search('Пьешь в таверне', text):
        hero_state = 'tavern'
    elif re.search('Возишься с КОРОВАНАМИ', text):
        hero_state = 'caravan'
    elif re.search('На стройке', text):
        hero_state = 'build'
    elif re.search('Атака на', text):
        hero_state = 'attack_ready'
    elif re.search('Защита', text):
        hero_state = 'defence_ready'
    else:
        log('Не удалось получить статус')
        send_msg('@', admin_username, 'Что-то пошло не так, не получилось распознать статус')


def go_to_arena():
    action_list.append(orders['castle_menu'])
    action_list.append('📯Арена')
    action_list.append('🔎Поиск соперника')
    log('Топаем на арену')


def go_to_building():
    log('Идём на стройку')
    action_list.append(building_target)


def building_available():
    global building_enabled
    global building_paused
    if building_enabled and not building_paused and hero_state == 'relax':
        return True
    return False


def arena_available():
    global gold
    global arena_enabled
    global arena_delay
    global arena_running
    global hero_state
    global tz
    if arena_enabled and not arena_delay and gold >= 5 and not arena_running and hero_state == 'relax':
        curhour = datetime.now(tz).hour
        if 9 <= curhour <= 23:
            return True
        return False
    return False


def go_to_quest():
    if peshera_enabled and endurance >= 2 and hero_state == 'relax':
        if les_enabled:
            action_list.append(orders['quests'])
            action_list.append(random.choice([orders['peshera'], orders['les']]))
        else:
            action_list.append(orders['quests'])
            action_list.append(orders['peshera'])

    elif les_enabled and not peshera_enabled and endurance >= 1 and orders['les'] not in action_list and hero_state == 'relax':
        action_list.append(orders['quests'])
        action_list.append(orders['les'])


def forest_end(text):
    if text.find('В кронах деревьев ты') != -1 or text.find('При прогулке по лесу тебя привлек еле заметный запах сосны') != -1 or text.find('В лесу ты отдохнул от бесконечных битв') != -1 or text.find('Ты вернулся из леса.') != -1:
        return True
    return False


def pre_battle_time():
    global tz
    hour = datetime.now(tz).hour
    minute = datetime.now(tz).minute
    if hour == 23 or hour == 3 or hour == 7 or hour == 11 or hour == 15 or hour == 19:
        if minute >= 40:
            return True
    return False


def after_battle_time():
    global tz
    hour = datetime.now(tz).hour
    minute = datetime.now(tz).minute
    if hour == 0 or hour == 4 or hour == 8 or hour == 12 or hour == 16 or hour == 20:
        if minute >= 10:
            return True
    return False


def send_msg(pref, to, message):
    sender.send_msg(pref + to, message)


def fwd(pref, to, message_id):
    sender.fwd(pref + to, message_id)


def update_order(order):
    current_order['order'] = order
    current_order['time'] = time()
    if order == castle:
        action_list.append(orders['cover'])
    else:
        action_list.append(orders['attack'])
    action_list.append(order)


def log(text):
    message = '{0:%Y-%m-%d+ %H:%M:%S}'.format(datetime.now()) + ' ' + text
    print(message)
    log_list.append(message)


if __name__ == '__main__':
    receiver = Receiver(sock=socket_path) if socket_path else Receiver(port=port)
    receiver.start()  # start the Connector.
    _thread.start_new_thread(queue_worker, ())
    receiver.message(work_with_message(receiver))
    receiver.stop()