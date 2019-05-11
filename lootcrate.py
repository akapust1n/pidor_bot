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


def keystoint(x):
    return {int(k): v for k, v in x.items()}


class LootCrates:
    def __init__(self, lootcrate_filename):
        self.lootcrate_filename = lootcrate_filename
        try:
            with open(lootcrate_filename, 'r') as f:
                filedata = f.read()
                self.data = json.loads(filedata, object_hook=keystoint)
        except:
            self.data = {}

    def grantLootCrate(self, bot, chatId, userId):
        lootcrate1 = "\n В этом сундуке могут быть: баны 0ч, 3ч, 6ч, 24ч(редкий) и СУПЕПРИРЗ - очко в пидоре дня!  \n " + \
            " АКЦИЯ: собери 20 неоткрытых сундуков и обменяй их на очко в пидоре дня!\n"
        text = "Вы выиграли сундук #1 ! https://market.games.mail.ru/media/product/picture/2019/4/979fb1d9d0721a124f805d282284348c.png ." + \
            lootcrate1+"\nОткрыть сундук /openlootcrate"
        self.addLootCrate(chatId, userId, 1)
        bot.send_message(
            chat_id=chatId, text=text)

    def addLootCrate(self, chatId, userId, lootCrateId):
        chat = self.data.get(chatId)
        if(chat is None):
            self.data[chatId] = {lootCrateId: {userId: 0}}
        elif self.data[chatId].get(lootCrateId) is None:
            self.data[chatId][lootCrateId] = {userId: 0}

        if(self.data[chatId][lootCrateId].get(userId) is None):
            self.data[chatId][lootCrateId][userId] = 1
        else:
            self.data[chatId][lootCrateId][userId] += 1
        self.commit()

    def rmLootCrate(self, chatId, userId, lootCrateId):
        try:
            if(self.data[chatId][lootCrateId][userId] > 0):
                self.data[chatId][lootCrateId][userId] -= 1
                self.commit()
                return True
        except:
            pass

        return False

    def commit(self):
        with open(self.lootcrate_filename, "w") as f:
            f.write(json.dumps(self.data))

    def getLootCratesList(self, chatId, lootCrateId):
        try:
            result = {}
            for user, count in self.data[chatId][lootCrateId].items():
                if(count > 0):
                    result[user] = count
            return result
        except:
            pass

        return None
