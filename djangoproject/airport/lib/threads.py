"""Thread classes and helpers for Airport"""
from logging import getLogger
from os import environ
from random import randint
from threading import Event, Thread, Timer
from time import sleep

from django.conf import settings
from tornado.ioloop import IOLoop
from tornado.web import Application

from airport.lib.websocket import IPCHandler, SocketHandler
from airport.models import Message

LOOP_DELAY = float(environ.get('GAMESERVER_LOOP_DELAY', '5'))
logger = getLogger('airport.threads')


class SocketServer(Thread):

    """Tornado web server in a thread.

    This server will handle WebSocket requests
    """
    daemon = True

    def run(self):
        logger.debug('%s has started', self.name)
        self.application = Application([(r"/", SocketHandler)])
        self.application.listen(settings.WEBSOCKET_PORT)

        self.ipc = Application([(r"/ipc", IPCHandler)])
        self.ipc.listen(settings.IPC_PORT, address='localhost')

        IOLoop.instance().start()

    @staticmethod
    def shutdown():
        logger.critical('Shutting down.')
        IOLoop.current().stop()


class Messenger(Thread):

    """Don't kill me ;-)"""
    daemon = True
    message_event = Event()

    def run(self):
        while True:
            self.message_event.wait()
            msgs_to_send = Message.objects.filter(
                read=False).order_by('profile', 'creation_time')
            for message in msgs_to_send:
                user = message.profile.user
                sent = SocketHandler.message(
                    user, 'message', message.to_dict())
                if sent:
                    message.mark_read()
            self.message_event.clear()


class GameThread(Thread):

    """A threaded loop that runs a game"""
    daemon = False

    def __init__(self, **kwargs):
        self.game = kwargs.pop('game')
        super(GameThread, self).__init__(**kwargs)

    def run(self):
        from airport import take_turn

        logger.info('Starting thread for game %s', self.game)
        self.fix_players()
        mw_gen = MonkeyWrenchGenerator()

        now = None

        while True:
            # re-fetch game
            game = self.game.__class__.objects.get(pk=self.game.pk)

            if game.state == game.GAME_OVER:
                logger.info('Game %s ended.', game)
                return

            ai_player = game.players.distinct().get(ai_player=True)
            ai_player.make_move(game, now)
            now = take_turn(game, throw_wrench=next(mw_gen))

            # send all messages for this cycle
            messenger.message_event.set()
            sleep(LOOP_DELAY)

    def fix_players(self):
        """Make sure players are not in a "weird" state."""
        # Like Texas.  This is needed for when the thread is
        # stopped/crashed and restarted.  Sometimes weird things can happen
        # like a player's plane has already landed but their ticket hasn't been
        # taken away.  So they end up in limbo... or Texas.
        fixed_players = []
        msg = 'Player %s had to be fixed.'

        for player in self.game.players.distinct():
            if not player.in_limbo(self.game):
                continue
            if player.ticket:
                player.airport = player.ticket.destination
                player.ticket = None
            else:
                player.airport = self.game.start_airport
            player.save()
            logger.info(msg % player.user.username)
            fixed_players.append(player)
        return fixed_players


class MonkeyWrenchGenerator(object):
    max_wait = 45

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
        Timer(randint(1, self.max_wait), self._set_throw).start()


messenger = Messenger()
