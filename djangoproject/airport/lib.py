import functools
import json
import logging
import multiprocessing
import os
import random
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import tornado
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from tornado import websocket
from tornado.ioloop import IOLoop
from tornado.web import Application

from . import models
from .conf import settings

LOOP_DELAY = settings.GAMESERVER_LOOP_DELAY
logger = logging.getLogger('airport.lib')

if settings.GAMESERVER_MULTIPROCESSING:
    GameThreadClass = multiprocessing.Process
else:
    GameThreadClass = threading.Thread


def start_game(game):
    """Start a Game and a GameThread to run it."""
    game.begin()
    send_message('start_game_thread', game.pk)


def take_turn(game, now=None, throw_wrench=True):
    now = now or game.time
    if game.state in (game.GAME_OVER, game.NOT_STARTED, game.PAUSED):
        return now

    winners_before = models.Player.objects.winners(game)
    arrivals = {}

    if not hasattr(game, '_airports'):
        game._airports = set(game.airports.distinct())

    if throw_wrench:
        send_message('throw_wrench', game.pk)

    for airport in game._airports:
        players_arrived = handle_flights(game, airport, now)
        for player in players_arrived:
            arrivals[player.pk] = airport

    handle_players(game, now, winners_before, arrivals)
    return now


def handle_flights(game, airport, now=None):
    announce = models.Message.objects.announce
    now = now or game.time
    players_arrived = []

    # Departing flights
    flights = set(airport.next_flights(now, auto_create=False))
    for flight in flights:
        in_flight = flight.in_flight(now)
        ticket_holders = flight.passengers.distinct()

        for player in ticket_holders:
            if not (in_flight and player.airport):
                continue

            # player has taken off
            player.airport = None
            player.save()
            game.record_ticket_purchase(player, flight)
            msg = '{0} has departed {1}.'
            msg = msg.format(player.user.username, airport)
            announce(player, msg, game, message_type='PLAYERACTION')

    # Arriving flights
    flights = models.Flight.objects.arrived_but_not_flagged(game, now)
    flights = flights.filter(destination=airport)  # for this airport

    for flight in flights:
        ticket_holders = flight.passengers.distinct()
        destination = flight.destination

        for player in ticket_holders:
            # player has landed
            msg = '{0} has arrived at {1}.'
            msg = msg.format(player.user.username, destination)
            announce(player, msg, game, message_type='PLAYERACTION')
            players_arrived.append(player)

            ach = player.next_goal(game)
            if ach and ach.goal.city == player.ticket.destination.city:
                ach.fulfill(player.ticket.arrival_time)

            player.airport = destination
            player.ticket = None
            player.save()

        flight.state = 'Arrived'
        flight.save()

    airport.next_flights(now, auto_create=True)
    return players_arrived


def handle_players(game, now, winners_before, arrivals):
    """Update each player in game."""
    # re-fetch the game in case it's paused
    game = models.Game.objects.get(pk=game.pk)
    broadcast = models.Message.objects.broadcast
    players = game.players.distinct()

    # FIXME: If the data previously sent hasn't changed, we shouldn't
    # re-send the data.  Actually, the data will almost always be the same
    # since we sent the time... so first we should probably work on not
    # sending the game time in each update... but since the game time is
    # different than "real" time, we can't rely on the client to know the
    # game time on its own.  Hmmm...
    for player in players:
        # if player is in another game, don't send any info. Doing so confuses
        # the client.
        current_game = player.current_game
        if current_game and current_game != game:
            continue
        player_info = player.info(game, now)
        if player.pk in arrivals:
            notify = 'You have arrived at {0}.'.format(arrivals[player.pk])
            player_info['notify'] = notify
        send_message('info', player_info)

    winners = models.Player.objects.winners(game)
    if not winners_before and winners:
        if len(winners) == 1:
            msg = '{0} has won {1}.'
            msg = msg.format(winners[0].user.username, game)
            broadcast(msg, game, message_type='WINNER', finishers=True)
        else:
            msg = '{0}: {1}-way tie for 1st place.'
            msg = msg.format(game, len(winners))
            broadcast(msg, game, message_type='WINNER', finishers=True)
            for winner in winners:
                msg = '{0} is a winner!'
                msg = msg.format(winner.user.username)
                broadcast(msg, game, message_type='WINNER', finishers=True)

    # if all players have achieved all goals, end the game
    if game.is_over():
        game.end()
        send_message('game_ended', game.pk)


def game_pause(game):
    if game.state == game.PAUSED:
        return game.host.info(game)
    game.pause()
    game = models.Game.objects.get(pk=game.pk)
    now = game.time
    host_info = {}
    for player in game.players.distinct():
        player_info = player.info(game, now)
        if player == game.host:
            host_info = player_info
        send_message('info', player_info)
    return host_info


def game_resume(game):
    if game.state != game.PAUSED:
        return game.host.info(game)
    game.resume()
    game = models.Game.objects.get(pk=game.pk)
    now = game.time
    host_info = {}
    for player in game.players.distinct():
        player_info = player.info(game, now)
        if player == game.host:
            host_info = player_info
        send_message('info', player_info)
    return host_info


def send_message(message_type, data):
    return IPCHandler.send_message(message_type, data)


def get_user_from_session_id(session_id):
    """Given the session_id, return the user associated with it.

    Raise User.DoesNotExist if session_id does not associate with a user.
    """
    try:
        session = Session.objects.get(session_key=session_id)
    except Session.DoesNotExist:
        raise User.DoesNotExist

    try:
        user_id = session.get_decoded().get('_auth_user_id')
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise
    return user


class WebSocketConnection(websocket.WebSocketHandler):

    def on_message(self, message):
        """Handle message"""
        message = json.loads(message)
        message_type = message['type']
        data = message['data']
        handler_name = 'handle_%s' % message_type
        logger.debug('Message received: %s' % message_type)

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
            client.write_message(json.dumps(
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
            client.write_message(json.dumps(
                {
                    'type': message_type,
                    'data': data,
                }
            ))

    @classmethod
    def games_info(cls):
        games = models.Game.games_info()
        for client in cls.clients:
            if client.page != 'games_menu':
                continue
            data = {}
            data['games'] = games

            if client.user and client.user.player.current_game:
                data.update(client.user.player.game_info())

            client.write_message(json.dumps(
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
    conn = None

    def open(self):
        logger.debug('IPC connection opened')

    def on_message(self, message):
        """Handle message"""
        message = json.loads(message)

        # Since IPC and "regular" websocket messages come on the same
        # (potentially open) port, we "sign" the IPC message with a pre-shared
        # key... what better key than Django's mandatory SECRET_KEY.  If the
        # key isn't sent or isn't our key, disregard the message.
        if message.get('key') != django_settings.SECRET_KEY:
            logger.critical('Someone is trying to hack me!', extra=message)
            return
        message_type = message['type']
        data = message['data']
        handler_name = 'handle_%s' % message_type
        logger.debug('Message received: %s' % message_type)

        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            handler(data)

    @staticmethod
    def get_conn():
        url = 'ws://%s:%s/ipc' % (settings.GAMESERVER_HOST,
                                  settings.WEBSOCKET_PORT)
        ioloop = tornado.ioloop.IOLoop()
        conn = ioloop.run_sync(functools.partial(
            tornado.websocket.websocket_connect, url))
        return conn

    @classmethod
    def send_message(cls, message_type, data):
        """
        Create a websocket connection and send a message to the handler.
        """
        cls.conn = cls.conn or cls.get_conn()
        cls.conn.write_message(json.dumps(
            {
                'type': message_type,
                'key': django_settings.SECRET_KEY,
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
        if settings.GAMESERVER_MULTIPROCESSING:
            connection.close()

        name = 'Game{0}'.format(game_id)
        game_thread = GameThread(name=name, game_id=game_id)
        game_thread.start()
        game = models.Game.objects.get(pk=game_id)
        for player in game.players.filter(ai_player=False).distinct():
            SocketHandler.message(player.user, 'join_game', {})
        SocketHandler.games_info()

    def handle_game_created(self, game_id):
        """Handler to for creating a game."""
        SocketHandler.games_info()

    def handle_game_ended(self, game_id):
        """Handler to for creating a game."""
        SocketHandler.games_info()

    def handle_game_paused(self, game_id):
        game = models.Game.objects.get(pk=game_id)
        for player in game.players.distinct():
            SocketHandler.message(player, 'info', player.info(game))
        SocketHandler.games_info()

    def handle_throw_wrench(self, game_id):
        game = models.Game.objects.get(pk=game_id)
        monkey_wrench = game.mwf.create(game)
        logger.info('Game {0}: throwing {0}.'.format(game, monkey_wrench))
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

    def handle_player_message(self, data):
        username = data['player']
        user = User.objects.get(username=username)
        message = data['message']
        SocketHandler.message(user, 'message', message)
# -----------------------------------------------------------------------------


class SocketServer(threading.Thread):

    """Tornado web server in a thread.

    This server will handle WebSocket requests
    """
    daemon = True

    def run(self):
        logger.debug('%s has started' % self.name)
        self.application = Application([
            (r'/', SocketHandler),
            (r'/ipc', IPCHandler),
        ])
        self.application.listen(settings.WEBSOCKET_PORT)
        IOLoop.instance().start()

    @staticmethod
    def shutdown():
        logger.critical('Shutting down.')
        IOLoop.current().stop()


class GameThread(GameThreadClass):

    """A threaded loop that runs a game"""
    daemon = False

    def __init__(self, **kwargs):
        self.game_id = kwargs.pop('game_id')

        super(GameThread, self).__init__(**kwargs)

    def run(self):
        logger.info('Starting thread for Game %s' % self.game_id)
        self.fix_players()
        mw_gen = MonkeyWrenchGenerator()
        executor = ThreadPoolExecutor(max_workers=4)

        now = None

        while True:
            timer = threading.Timer(LOOP_DELAY, lambda: None)
            timer.start()
            game = models.Game.objects.get(pk=self.game_id)
            ai_player = None

            if game.state == game.GAME_OVER:
                logger.info('Game {0} ended.', game.pk)
                return

            for ai_player in game.players.distinct().filter(ai_player=True):
                ai_player.make_move(game, now)

            now = take_turn(game, throw_wrench=next(mw_gen))

            # send all messages for this cycle
            executor.submit(self.send_messages)

            timer.join()

    def send_messages(self):
        # send all player messages (via IPC)
        msgs_to_send = models.Message.objects.filter(
            read=False).order_by('player', 'creation_time')
        for message in msgs_to_send:
            user = message.player.user
            IPCHandler.send_message(
                'player_message',
                {'player': user.username, 'message': message.to_dict()}
            )
            message.mark_read()

    def fix_players(self):
        """Make sure players are not in a "weird" state."""
        # Like Texas.  This is needed for when the thread is
        # stopped/crashed and restarted.  Sometimes weird things can happen
        # like a player's plane has already landed but their ticket hasn't been
        # taken away.  So they end up in limbo... or Texas.
        fixed_players = []
        msg = 'Game {0}: Player {1} had to be fixed.'
        game = models.Game.objects.get(pk=self.game_id)

        for player in game.players.distinct():
            if not player.in_limbo(game):
                continue
            if player.ticket:
                player.airport = player.ticket.destination
                player.ticket = None
            else:
                player.airport = game.start_airport
            player.save()
            logger.info(msg.format(game.pk, player.username))
            fixed_players.append(player)
        return fixed_players


class MonkeyWrenchGenerator(object):
    max_wait = settings.MAX_TIME_BETWEEN_WRENCHES

    def __init__(self):
        self._set_throw()
        self.throw_wrench = False

    def __iter__(self):
        return self

    def __next__(self):
        val = self.throw_wrench
        self.throw_wrench = False
        return val

    def _set_throw(self):
        self.throw_wrench = True
        threading.Timer(random.randint(1, self.max_wait),
                        self._set_throw).start()
