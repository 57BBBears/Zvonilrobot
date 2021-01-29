import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import asyncio
import aiohttp
from aiohttp import web

# TODO add format string for output message (before, result, after)
# TODO check input phone number
# TODO send info messages back during getting info (Starting..., Busy... etc.)
class Zvonilbot:
    def __init__(self, token: str, site: str, boturl='https://api.telegram.org/bot'):
        self.token = token
        self.boturl = boturl + token + '/'
        self.site = site
        self.update_id = None
        self._headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36'}
        self._delay = 0.2
        self._bot_timeout = 30
        # TODO add config

    async def getinfo(self, phone: str, session: aiohttp.ClientSession) -> dict:
        # TODO write specific function to write errors in file
        # TODO add parameter list with html tags i.g. div#id for searching on site
        """
        Get info about phone number.
        :param phone: str: phone to get info about
        :param: session: aiohttp.ClientSession: session for connection
        :return: dict: info about the phone. Keys: phone, head - short info, ratings, categories - categories which phone belongs to
        """
        head = []
        ratings = []
        categories = []
        error_msg = ''
        #headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36'}
        #TODO check phone
        async with session.get(self.site+phone, headers=self._headers) as r:
            try:
                assert r.status == 200
            except Exception as error:
                error_msg += '\r' + time.strftime('%d.%m.%Y %H:%M:%S',
                                                  time.localtime()) + ' | ' + phone + '| Connection | ' +\
                                                  str(r.status) + ' ' + str(error)
                print(error_msg)
                return {'errors': 'Connection error: ' + str(error)}

            html = await r.text()

        soup = BeautifulSoup(html, 'html.parser')
        try:
            head = soup.find('div', {'class': 'number'}).find_all('span')
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


    def getupdates(self, offset=''):
        params = {}
        if offset:
            #get update with offset explicitly
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

    async def sendmessage(self, chat_id: str, message: str, session: aiohttp.ClientSession):
        async with session.get(self.boturl+'sendMessage', params={'chat_id': chat_id, 'text': message}) as r:
            try:
                assert r.status == 200
            except Exception as error:
                error_msg = '\r' + time.strftime('%d.%m.%Y %H:%M:%S',
                                                 time.localtime()) + ' | ' + chat_id + ' | Send message | ' +\
                                                 str(r.status) + str(error)
                print(error_msg)
                return {'errors': 'Connection error: ' + error}
            else:
                answer = await r.json()
        """
        try:
            r = requests.get(self.boturl+'sendMessage', params={'chat_id': chat_id, 'text': message})
        except requests.exceptions.ConnectionError as error:
            error_msg = '\r'+time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' | ' + chat_id + ' | Send message | ' + str(error)
            print(error_msg)
            return {'errors': 'Connection error: '+error}

        if r.status_code != 200:
            return {'errors': 'Error status code: '+str(r.status_code)}
        

        answer = r.json()
        """

        if 'ok' in answer and answer['ok']:
            return answer
        else:
            return {'errors': answer}

    async def _getinfo_sendmessage(self, chat_id, phone, session):
        info = await self.getinfo(phone, session)
        print(info)
        if 'errors' in info:
            text = 'Упс! Что-то пошло не так. Попробуй ещё раз...'
        elif not info['ratings'] and not info['categories']:
            text = 'У меня ничего нет на него... Возможно это и не спам!'
        else:
            text = 'Так-так. Подозреваемый ' + info['phone'] + \
                   '\n\n\n'.join(info['head']) + \
                   '\n\nКатегории:' + '\n'.join(info['categories']) + \
                   '\n\nРейтинг:' + '\n'.join(info['ratings'])
        sent = await self.sendmessage(chat_id, text, session)
        if 'errors' in sent:
            print(sent['errors'])
            return sent['errors']
        else:
            print(sent)
            return sent


    async def _longpolling(self):
        while True:
            messages = self.getupdates()
            if messages and 'errors' not in messages:
                print(messages)

                limit = round(1 / self._delay) if self._delay != 0 else None
                connector = aiohttp.TCPConnector(limit=limit)
                async with aiohttp.ClientSession(connector=connector, headers=self._headers) as session:
                    for msg in messages:
                        phone = messages[msg]
                        info_task = await asyncio.create_task(self._getinfo_sendmessage(msg, phone, session))
                        print(time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' Done: '+str(info_task))


            else:
                print(time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())+' No updates...')
            await asyncio.sleep(self._bot_timeout)

    def longpolling(self):
        print('Longpolling started.')
        #asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        #asyncio.run(self._longpolling())
        loop = asyncio.get_event_loop()
        loop.create_task(self._longpolling())
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            loop.stop()
            exit('Longpolling stoped.')


    def startserver(self, route: str = '/'):
        app = web.Application()
        app.add_routes([web.get(route), self._webhook])
        web.run_app(app)

    async def _webhook(self, request):
        loop = asyncio.get_event_loop()
        async with aiohttp.ClientSession() as session:
            pass
        loop.run_forever()



if __name__ == '__main__':
    bot = Zvonilbot('1374908831:AAEv6e_nJ3JgsTD6HX82fSLlWAwXeTiNQEI', 'https://www.neberitrubku.ru/nomer-telefona/')
    bot.longpolling()
    """
    try:
        bot.longpolling()
    except KeyboardInterrupt:
        exit()
    """
    """
    msgs = bot.getupdates()
    if msgs and 'errors' not in msgs:
        for chat in msgs:
            print(str(chat)+':'+str(msgs[chat]))
    """
    #print(bot.sendmessage(chat_id='101633597', message='hello, world'))
    #info = bot.getinfo('89658203265')
    #print(info)