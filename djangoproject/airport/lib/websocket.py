import functools
from json import dumps, loads
import logging
import os
import sys
import signal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

import tornado.ioloop
import tornado.web
import tornado.websocket

from airport.lib import get_user_from_session_id
from airport.models import Game

logger = logging.getLogger('airport.websockets')


class WebSocketConnection(tornado.websocket.WebSocketHandler):

    def on_message(self, message):
        """Handle message"""
        message = loads(message)
        message_type = message['type']
        data = message['data']
        handler_name = 'handle_%s' % message_type
        logger.debug('Message received: %s', message_type)

        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            handler(data)


class SocketHandler(WebSocketConnection):
    clients = []

    def open(self):
        logger.debug('WebSocket connection opened')
        self.clients.append(self)
        self.broadcast('new_connection', self.user.username, exclude=[self])
        self.page = 'games_menu'

    def on_close(self):
        logger.debug('WebSocket connection closed')
        self.clients.remove(self)

    def on_pong(self, message):
        pass

    def get_current_user(self):
        if 'sessionid' not in self.request.cookies:
            return None
        session_id = self.request.cookies['sessionid'].value
        try:
            return get_user_from_session_id(session_id)
        except ObjectDoesNotExist:
            return None

    @property
    def user(self):
        return self.current_user

    @classmethod
    def message(cls, user, message_type, data):
        """Send a message to all connections associated with user"""
        clients = [i for i in cls.clients if i.user == user]
        for client in clients:
            if message_type == 'info' and client.page != 'home':
                continue
            client.write_message(dumps(
                {
                    'type': message_type,
                    'data': data,
                }
            ))
        return len(clients)

    @classmethod
    def broadcast(cls, message_type, data, exclude=None):
        exclude = exclude or []
        for client in cls.clients:
            if client in exclude:
                continue
            client.write_message(dumps(
                {
                    'type': message_type,
                    'data': data,
                }
            ))

    @classmethod
    def games_info(cls):
        games = Game.games_info()
        for client in cls.clients:
            if client.page != 'games_menu':
                continue
            data = {}
            data['games'] = games

            if client.user:
                profile = client.user.profile
                if profile.current_game is not None:
                    # we only care to give this info to users waiting on a game
                    continue
                data.update(profile.game_info())

            client.write_message(dumps(
                {
                    'type': 'games_info',
                    'data': data,
                }
            ))

    def handle_page(self, page):
        self.page = page


class IPCHandler(WebSocketConnection):
    """
    WebSocketHandler for ipc messages.
    """
    def open(self):
        logger.debug('IPC connection opened')

    def on_message(self, message):
        """Handle message"""
        message = loads(message)
        message_type = message['type']
        data = message['data']
        handler_name = 'handle_%s' % message_type
        logger.debug('Message received: %s', message_type)

        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            handler(data)

    @staticmethod
    def send_message(message_type, data):
        """
        Create a websocket connection and send a message to the handler.
        """
        url = 'ws://localhost:%s/ipc' % settings.IPC_PORT
        ioloop = tornado.ioloop.IOLoop()
        conn = ioloop.run_sync(functools.partial(
            tornado.websocket.websocket_connect, url))
        conn.write_message(dumps(
            {
                'type': message_type,
                'data': data,
            }
        ))

# - Message Handlers ----------------------------------------------------------
    def handle_info(self, info):
        """Handler for "info" data"""
        user = User.objects.get(username=info['player'])
        SocketHandler.message(user, 'info', info)

    def handle_start_game_thread(self, game_id):
        """Handler to start a Game thread."""
        # To get around circular imports
        from airport.lib.threads import GameThread

        game = Game.objects.get(pk=game_id)
        game_thread = GameThread(game=game)
        game_thread.start()
        SocketHandler.games_info()

    def handle_game_created(self, game_id):
        """Handler to for creating a game."""
        SocketHandler.games_info()

    def handle_game_ended(self, game_id):
        """Handler to for creating a game."""
        SocketHandler.games_info()

    def handle_game_paused(self, game_id):
        game = Game.objects.get(pk=game_id)
        for player in game.players.distinct():
            SocketHandler.message(player, 'info', player.info())
        SocketHandler.games_info()

    def handle_throw_wrench(self, game_id):
        game = Game.objects.get(pk=game_id)
        monkey_wrench = game.mwf.create(game)
        logger.info('throwing %s', monkey_wrench)
        monkey_wrench.throw()

    def handle_player_joined_game(self, data):
        SocketHandler.games_info()

    def handle_player_left_game(self, data):
        SocketHandler.games_info()

    def handle_wall(self, message):
        """Handler for wall messages."""
        SocketHandler.broadcast('wall', message)

    def handle_shutdown(self, data):
        """Shut down all services"""
        logger.critical('Shutting down')

        # suicide
        os.kill(os.getpid(), signal.SIGTERM)
        sys.exit(0)
# -----------------------------------------------------------------------------
