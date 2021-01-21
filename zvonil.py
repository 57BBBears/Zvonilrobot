import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import asyncio

class Zvonilbot:
    def __init__(self, token: str, site: str, boturl='https://api.telegram.org/bot'):
        self.token = token
        self.boturl = boturl + token + '/'
        self.site = site
        self.update_id = None

    def getinfo(self, phone: str) -> dict:
        #TODO write specific function to write errors in file
        """
        Get info about phone number.
        :param phone: str: phone to get info about
        :return: dict: info about the phone. Keys: phone, head - short info, ratings, categories - categories which phone belongs to
        """
        head = []
        ratings = []
        categories = []
        error_msg = ''
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36'}

        try:
            r = requests.get(self.site+phone, headers=headers)
        except requests.exceptions.ConnectionError as error:
            error_msg += '\r'+time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' | '+phone+'| Connection | ' + str(error)
            print(error_msg)
            return {'errors': 'Connection error: '+error}


        if r.status_code != 200:
            return {'errors': 'Error status code: '+str(r.status_code)}

        soup = BeautifulSoup(r.text, 'html.parser')
        try:
            head = soup.find('div', {'class': 'number1'}).find_all('span')
        except AttributeError as error:
            error_msg += '\r'+time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' | '+phone+' | div:number | ' + str(error)
            print(error_msg)
        else:
            head = [item.text for item in head]

        try:
            ratings = soup.find('div', {'class1': 'ratings'}).find_all('li')
        except AttributeError as error:
            error_msg += '\r'+time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' | '+phone+' | '+'div:ratings | ' + str(error)
            print(error_msg)
        else:
            ratings = [rate.text for rate in ratings]

        try:
            categories = soup.find('div', {'class': 'categories'}).find_all('li')
        except AttributeError as error:
            error_msg += '\r'+time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' | '+phone+' | div:categories | ' + str(error)
            print(error_msg)
        else:
            categories = [cat.text for cat in categories]
        print(error_msg)
        if error_msg:
            with open('error.txt', 'a', encoding='utf-8') as error_file:
                error_file.write(error_msg)

        return {'phone': phone, 'head': head, 'ratings': ratings, 'categories': categories}

        """
        with open('test.html', 'w', encoding='utf-8') as parse_file:
            parse_file.write(r.text)
        """

    def getupdates(self, offset='', timeout=30):
        params = {'timeout': timeout}
        if offset:
            params['offset'] = offset
        elif self.update_id is not None:
            params['offset'] = self.update_id+1

        try:
            r = requests.get(self.boturl+'getUpdates', params=params)
        except requests.exceptions.ConnectionError as error:
            error_msg = '\r'+time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' | '+offset+'| getUpdates | ' + str(error)
            print(error_msg)
            return {'errors': 'Connection error: '+error}

        answer = r.json()
        if answer['result']:
            self.update_id = answer['result'][-1]['update_id']
            chats = {}
            for res in answer['result']:
                chats[res['message']['chat']['id']] = res['message']['text']
            return chats
        else:
            return False


    def sendmessage(self, chat_id: str, message: str):
        try:
            r = requests.get(self.boturl+'sendMessage', params={'chat_id': chat_id, 'text': message})
        except requests.exceptions.ConnectionError as error:
            error_msg = '\r'+time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' | ' + chat_id + ' | Send message | ' + str(error)
            print(error_msg)
            return {'errors': 'Connection error: '+error}

        if r.status_code != 200:
            return {'errors': 'Error status code: '+str(r.status_code)}

        answer = r.json()

        if 'ok' in answer and answer['ok']:
            return answer
        else:
            return {'errors': answer}

    def longpolling(self):
        while True:
            messages = self.getupdates()
            if messages and 'errors' not in messages:
                for msg in messages:
                    phone = messages[msg]
                    info = self.getinfo(phone)
                    print(info)
                    text = 'Информация о номере ' + info['phone'] +\
                            '\r\r' + '\r'.join(info['head']) +\
                            '\r\rКатегории:' + '\r'.join(info['categories']) +\
                            '\r\rРейтинг:' + '\r'.join(info['ratings'])
                    sent = self.sendmessage(msg, text)
                    if 'errors' in sent:
                        print(sent['errors'])
                    else:
                        print(sent)



if __name__ == '__main__':
    bot = Zvonilbot('1374908831:AAEv6e_nJ3JgsTD6HX82fSLlWAwXeTiNQEI', 'https://www.neberitrubku.ru/nomer-telefona/')
    try:
        bot.longpolling()
    except KeyboardInterrupt:
        exit()
    """
    msgs = bot.getupdates()
    if msgs and 'errors' not in msgs:
        for chat in msgs:
            print(str(chat)+':'+str(msgs[chat]))
    """
    #print(bot.sendmessage(chat_id='101633597', message='hello, world'))
    #info = bot.getinfo('89658203265')
    #print(info)