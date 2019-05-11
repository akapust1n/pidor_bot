import os
import json
from random import choice
import random
import time
import functools
from datetime import datetime, timedelta
import datetime
import logging
import requests
import json
from datetime import datetime, timedelta


from telegram.ext import Updater, CommandHandler  # MessageHandler, filters
from telegram.chat import Chat
from lootcrate import LootCrates

from phrases import (
    GAME_RULES,
    common_phrases,
    scan_phrases,
    stats_phrases
)


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
logging.basicConfig(
    format='%(levelname)s [%(asctime)s] %(message)s', level=logging.INFO)


def requires_public_chat(func):
    @functools.wraps(func)
    def wrapped(self, bot, update, **kwargs):
        chat = update.message.chat
        if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            func(self, bot, update, **kwargs)
        else:
            Bot.send_answer(bot, chat.id, 'access_denied')
    return wrapped


def logged(func):
    @functools.wraps(func)
    def wrapped(self, bot, update, **kwargs):
        chat = update.message.chat
        user_id = update.message.from_user.id
        logging.info('[Chat: {}] Get command "{}" from user {}'.format(
            chat.id,
            func.__name__,
            Bot.get_username(chat, user_id)
        ))
        func(self, bot, update, **kwargs)
    return wrapped


class Bot:
    def __init__(self, token, memory_filename, ban_filename, lootcrate_filename):
        logging.info('Initializing bot...')
        self.updater = Updater(token=token)
        logging.info('Updater initialized')

        self.memory_filename = memory_filename
        self.ban_filename = ban_filename
        self.memory = self.load_memory()
        self.lootCrates = LootCrates(lootcrate_filename)
        logging.info('Memory loaded')

        self.today = None
        # self.echo_mode = False

        handlers = [
            CommandHandler('start', self.start),
            CommandHandler('pidorules', self.start),
            CommandHandler('shrug', self.shrug),
            CommandHandler('pidoreg', self.reg),
            CommandHandler('pidunreg', self.unreg),
            CommandHandler('pidor', self.choose_winner),
            CommandHandler('pidostats', self.stats),
            CommandHandler('rollBan', self.rollBan),
            #CommandHandler('test', self.test),
            #CommandHandler('test2', self.test2),
            CommandHandler('pidostats_lifetime', self.get_top_winners_all),
            CommandHandler('listlootcrates', self.list_lootcrates),
            CommandHandler('openlootcrate', self.openlootcrate),
            # CommandHandler('echo', self.echo),
            # MessageHandler(filters.Filters.all, self.echo_msg)
        ]

        for handler in handlers:
            self.updater.dispatcher.add_handler(handler)
        self.updater.dispatcher.add_error_handler(self.error_handler)
        logging.info('Handlers added')

    def start_polling(self):
        logging.info('Start polling...')
        self.updater.start_polling()

    # noinspection PyUnusedLocal
    @staticmethod
    def error_handler(bot, update, telegram_error):
        chat = update.message.chat
        logging.error('[Chat: {}] Got error {}: {}'.format(
            chat.id, type(telegram_error), telegram_error))

    def load_memory(self):
        try:
            with open(self.memory_filename, 'r') as f:
                raw_memory = json.load(f)
        except IOError:
            raw_memory = {}
        logging.info('Loading memory for {} chats...'.format(len(raw_memory)))
        memory = {}
        for chat_id, chat_memory in raw_memory.items():
            chat_memory['players'] = set(chat_memory['players'])
            memory[int(chat_id)] = chat_memory
        return memory

    def load_ban_memory(self):
        try:
            with open(self.ban_filename, 'r') as f:
                raw_memory = json.load(f)
        except:
            raw_memory = {}
        updatedate = raw_memory.get("updatetime")
        if(updatedate is None):
            raw_memory["updatetime"] = time.mktime(
                datetime.today().timetuple())
        date1 = datetime.fromtimestamp((int(raw_memory["updatetime"])))
        dt = datetime.today()
        if(date1.day != dt.day or updatedate is None):
            with open(self.ban_filename, "w+") as f:
                f.write(json.dumps({"updatetime": time.mktime(
                    datetime.today().timetuple())}))
        with open(self.ban_filename, 'r') as f:
            raw_memory = json.load(f)
        return raw_memory

    def get_memory(self, chat_id):
        return self.memory.setdefault(chat_id, {'players': set(), 'winners': {}})

    def commit_memory(self):
        def default(obj):
            if isinstance(obj, set):
                return list(obj)
            return json.JSONEncoder().default(obj)

        with open(self.memory_filename, 'w') as f:
            json.dump(self.memory, f, default=default)
        logging.info('Memory committed')

    def get_players(self, chat_id):
        return list(self.get_memory(chat_id)['players'])

    def add_player(self, chat_id, user_id):
        memory = self.get_memory(chat_id)
        memory['players'].add(user_id)
        logging.info('[Chat: {}] Updated players list: {}'.format(
            chat_id, list(memory['players'])))
        self.commit_memory()

    def remove_player(self, chat_id, user_id):
        memory = self.get_memory(chat_id)
        memory['players'].remove(user_id)
        logging.info('[Chat: {}] Updated players list: {}'.format(
            chat_id, list(memory['players'])))
        self.commit_memory()

    @staticmethod
    def get_current_date():
        return str((datetime.utcnow() + timedelta(hours=3)).date())

    def get_current_winner(self, chat_id):
        self.today = self.get_current_date()
        memory = self.get_memory(chat_id)
        winners = memory['winners']
        return winners.get(self.today, None)

    def set_current_winner(self, chat_id, user_id):
        if self.today is None:
            self.today = self.get_current_date()
        memory = self.get_memory(chat_id)
        winners = memory['winners']
        winners[self.today] = user_id
        logging.info('[Chat: {}] Updated winners: {}'.format(chat_id, winners))
        self.commit_memory()

    @requires_public_chat
    def get_top_winners_all(self, bot, update):  # копипаста -плохо
        message = update.message
        chat = message.chat
        chat_id = chat.id
        winners_by_date = self.get_memory(chat_id)['winners'].items()
        winners_by_id = {}
        for date, user_id in winners_by_date:
            winners_by_id.setdefault(user_id, []).append(date)
        logging.info(winners_by_id)
        sorted_winners = sorted(winners_by_id.items(),
                                key=lambda x: (-len(x[1]), min(x[1])))
        winners = list(map(lambda x: (x[0], len(x[1])), sorted_winners))[:10]

        if len(winners) > 0:
            text = [stats_phrases['header_all'], '']
            for i, (winner_id, victories_cnt) in enumerate(winners):
                text.append(stats_phrases['template'].format(num=i + 1,
                                                             name=self.get_username(
                                                                 chat, winner_id, call=False),
                                                             cnt=victories_cnt))
            text += ['', stats_phrases['footer'].format(
                players_cnt=len(self.get_players(chat.id)))]
            self.send_answer(bot, chat.id, text='\n'.join(text))
        else:
            self.send_answer(bot, chat.id, template='no_winners')

    def get_top_winners_of_the_month(self, chat_id):
        current_month = self.get_current_date()[:-3]
        winners_by_date = filter(lambda x: x[0].startswith(current_month),
                                 self.get_memory(chat_id)['winners'].items())
        winners_by_id = {}
        for date, user_id in winners_by_date:
            winners_by_id.setdefault(user_id, []).append(date)
        logging.info(winners_by_id)
        sorted_winners = sorted(winners_by_id.items(),
                                key=lambda x: (-len(x[1]), min(x[1])))
        return list(map(lambda x: (x[0], len(x[1])), sorted_winners))[:10]

    @staticmethod
    def get_username(chat, user_id, call=True):
        user = chat.get_member(user_id).user
        username = user.username
        if (username != '' and username is not None):
            username = '{}{}'.format('@' if call else '', username)
        else:
            username = user.first_name or user.last_name or user_id
        return username

    @logged
    def start(self, bot, update):
        self.send_answer(bot, update.message.chat_id, text=GAME_RULES)

    @logged
    @requires_public_chat
    def stats(self, bot, update):
        message = update.message
        chat = message.chat
        winners = self.get_top_winners_of_the_month(chat.id)

        if len(winners) > 0:
            text = [stats_phrases['header'], '']
            for i, (winner_id, victories_cnt) in enumerate(winners):
                text.append(stats_phrases['template'].format(num=i + 1,
                                                             name=self.get_username(
                                                                 chat, winner_id, call=False),
                                                             cnt=victories_cnt))
            text += ['', stats_phrases['footer'].format(
                players_cnt=len(self.get_players(chat.id)))]
            self.send_answer(bot, chat.id, text='\n'.join(text))
        else:
            self.send_answer(bot, chat.id, template='no_winners')

    @logged
    @requires_public_chat
    def list_players(self, bot, update):
        message = update.message
        chat = message.chat
        players = self.get_players(chat.id)
        if len(players) > 0:
            for i in range(0, len(players), 10):
                players = [self.get_username(chat, player_id)
                           for player_id in players[i:i+10]]
                text = ' '.join(players)
                if i == 0:
                    header = common_phrases['list_players_header']
                    text = '{}\n{}'.format(header, text)
                self.send_answer(bot, chat.id, text=text)
        else:
            self.send_answer(bot, chat.id, template='no_players')

    @requires_public_chat
    def rollBan(self, bot, update):
        random.seed(a=None, version=2)
        message = update.message
        chat = message.chat
        userid = message.from_user.id
        winners = self.get_top_winners_of_the_month(
            chat.id)  # todo кэширование

        member = chat.get_member(int(userid))
        if member is None or member.can_send_messages is False:
            bot.send_message(
                chat_id=chat.id, text="вы уже забанены 👀")
            return

        memoryRaw = self.load_ban_memory()
        players = memoryRaw.get("players")
        memory = {}

        if(players is None):
            memory["players"] = []
        else:
            memory["players"] = players
        count = memory["players"].count(userid)

        currentMonthWictories = 0
        for i, (winner_id, victories_cnt) in enumerate(winners):
            if winner_id == userid:
                currentMonthWictories = victories_cnt

        personalCount = 3 + currentMonthWictories
        if(count > personalCount):
            chance = random.randint(1, 2)
            text = "вы исчерпали свой лимит попыток на сегодня :("
            if chance > 1:
                text = text + " Играйте в пидора дня и получайте больше роллов!"
            bot.send_message(
                chat_id=chat.id, text=text)
        else:
            memory["players"].append(userid)

            with open(self.ban_filename, "w+") as f:
                memoryRaw["players"] = memory["players"]
                f.write(json.dumps(memoryRaw))

            chance = random.randint(1, 1000)
            rarity = "Common"
            timeMinutes = 0

            lootcrateChance = 300 if datetime.now().day == 12 else 150
            if(chance > 997):

                rarity = "Legendary"
                bot.send_message(chat_id=chat.id, text="ЛЕГЕНДА!!!!!!")
                bot.send_message(
                    chat_id=chat.id, text="https://www.youtube.com/watch?v=Dqf1BmN4Dag !!!!!!")
                bot.send_message(
                    chat_id=chat.id, text="Ваш ЛЕГЕНДАРНЫЙ приз будет зачислен вам в ближайшее время.")
            if(chance > 970):
                timeMinutes = random.randint(960, 1200)
                rarity = "Mythical"
            elif (chance > 880):
                timeMinutes = random.randint(280, 360)
                rarity = "Rare"
            elif(chance > 650):
                timeMinutes = random.randint(60, 120)
                rarity = "Uncommon"
            elif(chance > lootcrateChance):
                timeMinutes = random.randint(10, 20)
            else:
                self.lootCrates.grantLootCrate(bot, chat.id, userid)
                return

            time_from_now = datetime.now() + timedelta(minutes=timeMinutes)
            if(rarity != "legendary"):
                answer = "Поздравляем, вы выиграли _*{}*_ бан. Время вашего бана - {} минут".format(
                    rarity, timeMinutes)

            r = requests.get(
                "https://meme-api.herokuapp.com/gimme")
            if(r.status_code == 200):
                temp = r.json()
                mem = temp['url']
                if mem is not None:
                    bot.send_message(chat_id=chat.id, text=mem)
                    bot.send_message(
                        chat_id=chat.id, text=answer, parse_mode='Markdown')
                    bot.restrict_chat_member(
                        chat_id=chat.id, user_id=userid, until_date=time_from_now)

    def test(self, bot, update):
        chat = update.message.chat
        userid = update.message.from_user.id
        self.lootCrates.addLootCrate(chat.id, userid, 1)

    def test2(self, bot, update):
        chat = update.message.chat
        userid = update.message.from_user.id
        # self.lootCrates.rmLootCrate(chat.id, userid, 1)
        self.lootCrates.getLootCratesList(chat.id, 1)

        # determine chatid
        # message = update.message
        # chat = message.chat
        # arr = []  # determine pairs userid-username
        # for i in arr:
        # self.get_username(message.chat, user_id=i)
    @requires_public_chat
    def list_lootcrates(self, bot, update):
        message = update.message
        chat = message.chat
        chat_id = chat.id
        players = self.lootCrates.getLootCratesList(chat_id, 1)
        if(players is None):
            self.send_answer(
                bot, chat.id, text='На складе сундуков пусто! 🗑️')  # copypaste
            return

        sorted_players = sorted(
            players.items(), key=lambda kv: kv[1], reverse=True)
        sorted_players = sorted_players[:10]
        if len(sorted_players) > 0:
            text = [stats_phrases['header_lootcrate1'], '']
            for i, (playerId, lootCrateCount) in enumerate(sorted_players):  # there should be
                text.append(stats_phrases['template_lootcrate'].format(num=i + 1,
                                                                       name=self.get_username(
                                                                           chat, playerId, call=False),
                                                                       cnt=lootCrateCount))
           # text += ['', stats_phrases['footer_lootcrate'].format( TODO
             #   players_cnt=len(self.get_players(chat.id)))]
            self.send_answer(bot, chat.id, text='\n'.join(text))
        else:
            self.send_answer(bot, chat.id, text='На складе сундуков пусто! 🗑️')

    @requires_public_chat
    def openlootcrate(self, bot, update):
        random.seed(a=None, version=2)
        message = update.message
        chat = message.chat
        userid = update.message.from_user.id
        chance = random.randint(1, 1000)
        timeMinutes = 0

        if(self.lootCrates.rmLootCrate(chat.id, userid, 1)):
            # for lootcrate 1 . TODO resource system
            if(chance > 990):  # todo normal chance
                text = "Вы выиграли уникальный приз сундука #1! Приз будет зачислен в ближайшее время"
                bot.send_message(chat_id=chat.id, text=text)
                return

            if(chance > 900):
                timeMinutes = 24*60
            elif (chance > 700):
                timeMinutes = 6*60
            elif(chance > 200):
                timeMinutes = 3*60

            time_from_now = datetime.now() + timedelta(minutes=timeMinutes)

            answer = "Дроп: бан - {} минут!".format(timeMinutes)
            bot.send_message(
                chat_id=chat.id, text=answer, parse_mode='Markdown')
            bot.restrict_chat_member(
                chat_id=chat.id, user_id=userid, until_date=time_from_now)
        else:
            bot.send_message(
                chat_id=chat.id, text="У вас нет сундуков 😢")

    @logged
    @requires_public_chat
    def reg(self, bot, update):
        message = update.message
        chat = message.chat
        user_id = message.from_user.id
        if user_id in self.get_players(chat.id):
            answer_template = 'already_in_the_game'
        else:
            self.add_player(chat.id, user_id)
            answer_template = 'added_to_the_game'
        self.send_answer(bot, chat.id, template=answer_template)

    @logged
    @requires_public_chat
    def unreg(self, bot, update):
        message = update.message
        chat = message.chat
        user_id = message.from_user.id
        if user_id not in self.get_players(chat.id):
            answer_template = 'not_in_the_game'
        else:
            self.remove_player(chat.id, user_id)
            answer_template = 'removed_from_the_game'
        self.send_answer(bot, chat.id, template=answer_template)

    @logged
    @requires_public_chat
    def choose_winner(self, bot, update):
        random.seed(a=None, version=2)
        message = update.message
        chat = message.chat
        current_winner = self.get_current_winner(chat.id)

        if current_winner is not None:
            user = chat.get_member(current_winner).user
            username = self.get_username(message.chat, user_id=current_winner)
            self.send_answer(
                bot, chat.id, template='winner_known', name=username)
        else:
            players = self.get_players(chat.id)
            if len(players) == 0:
                self.send_answer(bot, chat.id, template='no_players')
            elif len(players) == 1:
                self.send_answer(bot, chat.id, template='only_one_player')
            else:
                for i in range(3):
                    phrase = choice(scan_phrases[i])
                    self.send_answer(bot, chat.id, text=phrase)
                    time.sleep(1.5)
                playersCopy = players.copy()
                numberOfShuffles = random.randint(1, 101)
                for _ in range(numberOfShuffles):
                    random.shuffle(playersCopy)

                selected = choice(playersCopy)
                self.set_current_winner(chat.id, selected)
                selected_name = self.get_username(
                    message.chat, user_id=selected)
                last_phrase = choice(
                    scan_phrases[-1]).format(name=selected_name)
                self.send_answer(bot, chat.id, text=last_phrase)

    @logged
    def shrug(self, bot, update):
        self.send_answer(bot, update.message.chat_id, text='¯\_(ツ)_/¯')

    # def echo(self, bot, update):
    #     chat = update.message.chat
    #     user_id = update.message.from_user.id
    #     logging.info('[Chat: {}] Get command "chat" from user {}'.format(chat.id, self.get_username(chat, user_id)))
    #     if chat.id == 122377527:
    #         if self.echo_mode:
    #             self.send_answer(bot, chat.id, template='echo_finished')
    #             self.echo_mode = False
    #         else:
    #             self.send_answer(bot, chat.id, template='echo_started')
    #             self.echo_mode = True

    # def echo_msg(self, bot, update):
    #     message = update.message
    #     chat = message.chat
    #     if chat.id == 122377527 and self.echo_mode:
    #         self.send_answer(bot, -151166400, text=message.text)

    @staticmethod
    def send_answer(bot, chat_id, template=None, text=None, **kwargs):
        if text is None:
            text = common_phrases[template].format(**kwargs)
        logging.info('[Chat: {}] Sending response: {}'.format(chat_id, text))
        bot.sendMessage(chat_id=chat_id, text=text, parse_mode='html')


if __name__ == '__main__':
    with open(os.path.join(SCRIPT_DIR, 'token.txt')) as token_file:
        token_ = token_file.readline().strip()

    mem_filename = os.path.join(os.environ.get(
        'MEMORY_DIR', SCRIPT_DIR), 'memory_dump.json')
    ban_filename = os.path.join(os.environ.get(
        'MEMORY_DIR', SCRIPT_DIR), 'ban_dump.json')
    lootcrate_filename = os.path.join(os.environ.get(
        'MEMORY_DIR', SCRIPT_DIR), 'lootcrate.json')
    bot_ = Bot(token=token_, memory_filename=mem_filename,
               ban_filename=ban_filename, lootcrate_filename=lootcrate_filename)
    bot_.start_polling()
