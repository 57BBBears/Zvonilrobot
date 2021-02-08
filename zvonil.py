import re
import requests
from bs4 import BeautifulSoup
import time
import asyncio
import aiohttp
from aiohttp import web
import json

# TODO add format string for output message (before, result, after)
# TODO check input phone number
# TODO send info messages back during getting info (Starting..., Busy... etc.)
class Zvonilbot:
    BOT_URL = 'https://api.telegram.org/bot'

    def __init__(self, token: str, site: str = 'https://www.neberitrubku.ru/nomer-telefona/'):
        self.token = token
        self.boturl = self.BOT_URL + token + '/'
        self.site = site
        self.update_id = None
        self._headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36'}
        self._delay = 0.2
        self._bot_timeout = 30
        # TODO add messages pattern (error, success, ok, etc)
        self.message = {'wrong number': 'Ыть! Неправильно набран номер.\nПопробуй использовать цифры.',
                        'error': 'Упс! Что-то пошло не так. Попробуй ещё раз...',
                        'ok': '{}\nУ меня ничего нет на него... Возможно это и не спам!',
                        'not ok': 'Так-так. Подозреваемый {phone} \
                                   \n\n{head} \
                                   \n\nКатегории:\n{categories}\
                                   \n\nРейтинг:\n{ratings}'}
        # TODO add config

    def _check_phone(self, string: str, pattern: str = '', delete: str = '') -> str:
        if delete:
            string = re.sub(delete, '', string)

        if pattern:
            check = re.match(pattern, string)

        if not check:
            return ''
        else:
            # russian number without 8 at the begining
            if string[0] == '9':
                string = '8' + string

            return string

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
            head = [item.text.strip() for item in head]

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
        # TODO replace with async log
        if error_msg:
            with open('error.txt', 'a', encoding='utf-8') as error_file:
                error_file.write(error_msg)

        return {'phone': phone, 'head': head, 'ratings': ratings, 'categories': categories}

    async def phone_to_msg(self, phone: str, session: aiohttp.ClientSession) -> str:
        phone = self._check_phone(phone, r'^(8|7|\+)?\d{10,12}$', r' |\-|\(|\)')
        if not phone:
            text = self.message['wrong number']
        else:
            info = await self.getinfo(phone, session)

            print(info)
            if 'errors' in info:
                text = self.message['send error']
            elif not info['ratings'] and not info['categories']:
                text = self.message['ok'].format(phone)
            else:
                text = self.message['not ok'].format(phone=phone,
                                                     head='\n'.join(info['head']),
                                                     categories='\n'.join(info['categories']),
                                                     ratings='\n'.join(info['ratings']))
        return text

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
        headers = {
            'Content-Type': 'application/json'
        }
        message = {
            'chat_id': chat_id,
            'text': message
        }

        #async with session.get(self.boturl+'sendMessage', params={'chat_id': chat_id, 'text': message}) as r:
        async with session.post(self.boturl+'sendMessage', data=json.dumps(message), headers=headers) as res:
            try:
                assert res.status == 200
            except Exception as error:
                error_msg = '\r' + time.strftime('%d.%m.%Y %H:%M:%S',
                                                 time.localtime()) + ' | ' + chat_id + ' | Send message | ' +\
                                                 str(res.status) + str(error)
                print(error_msg)
                return {'errors': 'Sending message error: ' + error}
            else:
                answer = await res.json()

        if 'ok' in answer and answer['ok']:
            return answer
        else:
            return {'errors': answer}

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



    async def _getinfo_sendmessage(self, chat_id: str, phone: str, session: aiohttp.ClientSession):
        text = await self.phone_to_msg(phone, session)
        sent = await self.sendmessage(chat_id, text, session)
        if 'errors' in sent:
            print(sent['errors'])
            return sent['errors']
        else:
            print(sent)
            return sent
        """
        phone = self._check_phone(phone, r'^(8|7|\+)?\d{10,12}$', r' |\-|\(|\)')
        if phone:
            text = await self.phone_to_msg(phone, session)
        else:
            text = self.message['wrong number']

        
            return await self.sendmessage(chat_id, text, session)
        print(info)
        if 'errors' in info:
            text = self.message['send error']
        elif not info['ratings'] and not info['categories']:
            text = self.message['ok'].format(phone)
        else:
            text = self.message['not ok'].format(phone=phone,
                                                 head='\n'.join(info['head']),
                                                 categories='\n'.join(info['categories']),
                                                 ratings='\n'.join(info['ratings']))
        """

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
        print('Long polling has started. (Press CTRL+C to stop)')
        #asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        #asyncio.run(self._longpolling())
        loop = asyncio.get_event_loop()
        loop.create_task(self._longpolling())
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            loop.stop()
            exit('Long polling has stopped.')


    def startserver(self, route: str = '/'):
        print('Server has started.')
        app = web.Application()
        app.add_routes([web.get(route, self._startserver)])
        web.run_app(app)
        print('Server has stopped.')

    async def _webhook(self, request):
        data = await request.json()
        chat_id = data['message']['chat']['id']
        phone = data['message']['text']
        phone = self._check_phone(phone, r'^(8|7|\+)?\d{10,12}$', r' |\-|\(|\)')

        async with aiohttp.ClientSession() as session:
            text = await self.phone_to_msg(phone, session)
            resp = await self.sendmessage(chat_id, text, session)

        if 'errors' in resp:
            return web.Response(500)
        else:
            return web.Response(200)


if __name__ == '__main__':
    bot = Zvonilbot('1374908831:AAEv6e_nJ3JgsTD6HX82fSLlWAwXeTiNQEI')
    #bot.longpolling()
    bot.startserver()
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