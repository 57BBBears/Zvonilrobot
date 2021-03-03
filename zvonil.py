import re
from bs4 import BeautifulSoup
import asyncio
import aiohttp
from aiohttp import web
import json
import logging.config
import sys


# TODO add format string for output message (before, result, after)
# TODO send info messages back during getting info (Starting..., Busy... etc.)
class Zvonilbot:
    BOT_URL = 'https://api.telegram.org/bot'

    def __init__(self, token: str, site: str = 'https://www.neberitrubku.ru/nomer-telefona/'):
        self.token = token
        self.boturl = self.BOT_URL + token + '/'
        self.site = site
        self.update_id = None
        self._headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36'}
        # Pause between connections for parser
        self._delay = 0.2
        # Pause between getting bot updates
        self._bot_timeout = 30
        self.session = None
        self.logger = self.get_logger()
        self.message = {'start': 'Проверю номер телефона на спам и роботов. Жду номер...',
                        'wrong number': 'Ыть! Неправильно набран номер.\nПопробуй использовать цифры.',
                        'error': 'Упс! Что-то пошло не так. Попробуй ещё раз...',
                        'ok': 'Хм... {} У меня ничего нет на него... Возможно это и не спам!',
                        'not ok': 'Так-так. Подозреваемый {phone} \
                                   \n\n{head} \
                                   \n\nКатегории\n{categories}\
                                   \n\nРейтинг\n{ratings}',
                        404: 'Номер не найден ^.^ Проверь номер и попробуй ещё раз.'}
        # TODO add config
    
    def get_logger(self, log_format='%(asctime)s:%(name)s:%(message)s',
               console_lvl='DEBUG', info_lvl='INFO', error_lvl='ERROR', config=None):
        """
        Logger for logging requests to bot and errors.
        :param log_format: Format string for logger output. Default: '%(asctime)s:%(name)s:%(message)s'
        :param console_lvl: Output level for console messages. Default: 'ERROR'
        :param info_lvl: Output level for requests to bot. Default: 'INFO'
        :param error_lvl: Output level for error messages. Default: 'ERROR'
        :param config: full config for all options
        :return: logger instance
        """
        if not config:
            config = {
                'version': 1,
                'disable_existing_loggers': True,
                'formatters': {
                    'standard': {
                        'format': log_format
                    },
                },
                'handlers': {
                    'console': {
                        'level': console_lvl,
                        'formatter': 'standard',
                        'class': 'logging.StreamHandler',
                        'stream': 'ext://sys.stdout',
                    },
                    'bot': {
                        'level': info_lvl,
                        'formatter': 'standard',
                        'class': 'logging.handlers.RotatingFileHandler',
                        'filename': 'bot.log',
                        'maxBytes': 50_000_024,
                        'backupCount': 10,
                        'encoding': 'utf-8'
                    },
                    'error': {
                        'level': error_lvl,
                        'formatter': 'standard',
                        'class': 'logging.handlers.RotatingFileHandler',
                        'filename': 'error.log',
                        'maxBytes': 10_000_024,
                        'backupCount': 10,
                        'encoding': 'utf-8'
                    }
                },
                'loggers': {
                    __name__: {
                        'handlers': ['console', 'bot', 'error'],
                        'level': 'DEBUG',
                        #'propagate': True,
                    }
                },
            }
        else:
            config = config

        logging.config.dictConfig(config)
        """
        logger.setLevel(logging.INFO)
        log_format = self.log_format

        #console error messages
        console = logging.StreamHandler()
        console.setFormatter(log_format)
        console.setLevel(console_lvl)
        #write all requests to a file
        bot_handler = logging.handlers.RotatingFileHandler('bot.log', maxBytes=50_000_024, backupCount=10)
        bot_handler.setFormatter(log_format)
        bot_handler.setLevel(info_lvl)
        #write errors to a file
        error_handler = logging.handlers.RotatingFileHandler('error.log', maxBytes=10_000_024, backupCount=10)
        error_handler.setFormatter(log_format)
        error_handler.setLevel(error_lvl)

        logger.addHandler(bot_handler)
        logger.addHandler(error_handler)
        logger.addHandler(console)
        """
        # bot handler log just info messages
        logger = logging.getLogger(__name__)
        logger.handlers[1].addFilter(type('', (logging.Filter,),
                                          {'filter': staticmethod(lambda r: r.levelno == logging.INFO)}))
        return logger

    def _check_phone(self, string: str, pattern: str = '', delete: str = '') -> str:
        check = False

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
                if r.status == 404:
                    self.logger.error(phone + ':Parser 404 error. ' + str(r.status) + ' ' + str(error))
                    return {'error': 404}
                else:
                    self.logger.error(phone+':Parser connection error. '+str(r.status) + ' ' + str(error))
                    return None

            html = await r.text()

        soup = BeautifulSoup(html, 'html.parser')
        try:
            head = soup.find('div', {'class': 'number'}).find_all('span')
        except AttributeError as error:
            error_msg += 'Can\'t find div number. ' + str(error)
        else:
            head = [item.text.strip() for item in head]

        try:
            ratings = soup.find('div', {'class': 'ratings'}).find_all('li')
        except AttributeError as error:
            error_msg += '\nCan\'t find div ratings. ' + str(error)
        else:
            ratings = [rate.text for rate in ratings]

        try:
            categories = soup.find('div', {'class': 'categories'}).find_all('li')
        except AttributeError as error:
            error_msg += '\nCan\'t find div categories. ' + str(error)
        else:
            categories = [cat.text for cat in categories]

        if error_msg:
            self.logger.warning(phone+':'+error_msg)

        return {'phone': phone, 'head': head, 'ratings': ratings, 'categories': categories}

    async def phone_to_msg(self, phone: str, session: aiohttp.ClientSession) -> str:
        phone = self._check_phone(phone, r'^(8|7|\+)?\d{10,12}$', r' |\-|\(|\)')
        if not phone:
            text = self.message['wrong number']
        else:
            info = await self.getinfo(phone, session)

            if not info:
                text = self.message['error']
            elif 'error' in info:
                text = self.message[info['error']]
            elif not info['ratings'] and not info['categories']:
                text = self.message['ok'].format(phone)
            else:
                text = self.message['not ok'].format(phone=phone,
                                                     head='\n'.join(info['head']),
                                                     categories='\n'.join(info['categories']),
                                                     ratings='\n'.join(info['ratings']))
        return text

    async def getupdates(self, session, offset=''):
        params = {}
        if offset:
            # get update with offset explicitly
            params['offset'] = offset
        elif self.update_id is not None:
            params['offset'] = self.update_id+1

        async with session.get(self.boturl + 'getUpdates', params=params) as res:
            try:
                assert res.status == 200
            except Exception as error:
                self.logger.error(':Can\'t get bot updates. ' + res.status + error)
                return None
            else:
                answer = await res.json()

        if answer['result']:
            self.update_id = answer['result'][-1]['update_id']
            chats = {}
            for res in answer['result']:
                chats[res['message']['chat']['id']] = res['message']['text']
            return chats
        else:
            return None

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
                self.logger.error('::Can\'t send message to bot. Chat ' + chat_id + '.'+str(res.status) + str(error))
                return None
            else:
                answer = await res.json()

        if 'ok' in answer and answer['ok']:
            return answer
        else:
            self.logger.error('::Not ok response from bot while sending message. Chat ' + chat_id + '.')
            return None

    async def _getinfo_sendmessage(self, chat_id: str, phone: str, session: aiohttp.ClientSession):
        if phone == '/start':
            text = self.message['start']
        else:
            text = await self.phone_to_msg(phone, session)
        sent = await self.sendmessage(chat_id, text, session)
        if sent:
            return sent
        else:
            return None

    def _get_session(self):
        if not self.session:
            limit = round(1 / self._delay) if self._delay != 0 else 0
            connector = aiohttp.TCPConnector(limit_per_host=limit)
            self.session = aiohttp.ClientSession(connector=connector, headers=self._headers)
        return self.session

    async def _longpolling(self):
        """
        limit = round(1 / self._delay) if self._delay != 0 else 0
        connector = aiohttp.TCPConnector(limit_per_host=limit)
        async with aiohttp.ClientSession(connector=connector, headers=self._headers) as session:
        """
        session = self._get_session()
        while True:
            messages = await self.getupdates(session)
            if messages:
                #async with aiohttp.ClientSession(connector=connector, headers=self._headers) as session:
                info_task = []
                for msg in messages:
                    phone = messages[msg]
                    info_task.append(self._getinfo_sendmessage(msg, phone, session))
                    #info_task[phone] = asyncio.create_task(self._getinfo_sendmessage(msg, phone, session))

                results = await asyncio.gather(*info_task)
                for msg, res in zip(messages, results):
                    phone = messages[msg]
                    if res:
                        self.logger.info(phone + ':Done!')
                    else:
                        self.logger.error(phone + ':Some problems occurred!')
            else:
                self.logger.debug(':No updates...')
            await asyncio.sleep(self._bot_timeout)

    # TODO prevent getting last update after restarting longpolling
    def longpolling(self):
        self.logger.debug('Long polling has started. (Press CTRL+C to stop)')
        #asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        #asyncio.run(self._longpolling())
        loop = asyncio.get_event_loop()
        loop.create_task(self._longpolling())
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            loop.stop()
            self.logger.debug('Long polling has stopped.')
            exit()

    def start_server(self, route: str = '/'):
        print('Server has started.')
        app = web.Application()
        app.add_routes([web.get(route, self._webhook)])
        web.run_app(app)
        print('Server has stopped.')

    async def _webhook(self, request):
        """
        try:
            json.loads(request)
        except ValueError as error:
            self.logger.error(':Bad request: ' + request)
            return web.Response(status=500, text='')
        """
        try:
            # TODO test content type
            if request.content_type != 'application/json':
                self.logger.error(':Bad request: ' + request.content_type + await request.text())
                return web.Response(status=500, text='')
        except AttributeError:
            # request is a string
            data = json.loads(request)
        else:
            # request is a aiohttp.web.Request
            data = await request.json()

        # check type of msg (message/edited) and protect against bots
        if 'message' in data and data['message'] and not data['message']['from']['is_bot']:
            key = 'message'
        elif 'edited_message' in data and data['edited_message'] and not data['edited_message']['from']['is_bot']:
            key = 'edited_message'
        else:
            return web.Response(status=500, text='')

        chat_id = data[key]['chat']['id']
        phone = data[key]['text']

        session = self._get_session()
        # async with aiohttp.ClientSession() as session:

        if phone == '/start':
            text = self.message['start']
        else:
            phone = self._check_phone(phone, r'^(8|7|\+)?\d{10,12}$', r' |\-|\(|\)')
            if not phone:
                text = self.message['wrong number']
            else:
                text = await self.phone_to_msg(phone, session)

        resp = await self.sendmessage(chat_id, text, session)

        if resp:
            self.logger.info(f'{phone}:{chat_id}:{text}')
            return web.Response(status=200, text='')
        else:
            self.logger.error(f'{phone}:{chat_id}:Some problems occurred!')
            return web.Response(status=500, text='')

    def start_running(self):
        #stop console output to prevent writing to html
        self.logger.removeHandler(self.logger.handlers[0])
        post = sys.stdin.read()
        if post:
            loop = asyncio.get_event_loop()
            response = loop.run_until_complete(self._webhook(post))
            if response.status == 200:
                print("Status: 200")
                print("Content-Type: text/html\n")

        print('Status: 500')
        print("Content-Type: text/html\n")


if __name__ == '__main__':
    bot = Zvonilbot('API Token')
    #bot.longpolling()
    #bot.startserver()
    bot.start_running()
