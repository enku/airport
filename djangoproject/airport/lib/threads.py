"""Thread classes and helpers for Airport"""
from logging import getLogger
from random import randint
from threading import Event, Thread, Timer

from tornado.ioloop import IOLoop
from tornado.web import Application

from airport.conf import settings
from airport.lib.websocket import IPCHandler, SocketHandler
from airport.models import Message

LOOP_DELAY = settings.GAMESERVER_LOOP_DELAY
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
        self.has_ai_player = self.game.players.filter(ai_player=True).exists()
        self.turn_event = Event()

        super(GameThread, self).__init__(**kwargs)

    def run(self):
        from airport import take_turn

        logger.info('Starting thread for %s', self.game)
        self.fix_players()
        mw_gen = MonkeyWrenchGenerator()

        now = None

        while True:
            Timer(LOOP_DELAY, self.turn_event.set).start()
            # re-fetch game
            game = self.game.__class__.objects.get(pk=self.game.pk)

            if game.state == game.GAME_OVER:
                logger.info('%s ended.', game)
                return

            if self.has_ai_player:
                ai_player = game.players.distinct().get(ai_player=True)
                ai_player.make_move(game, now)

            now = take_turn(game, throw_wrench=next(mw_gen))

            # send all messages for this cycle
            messenger.message_event.set()

            self.turn_event.wait()
            self.turn_event.clear()

    def fix_players(self):
        """Make sure players are not in a "weird" state."""
        # Like Texas.  This is needed for when the thread is
        # stopped/crashed and restarted.  Sometimes weird things can happen
        # like a player's plane has already landed but their ticket hasn't been
        # taken away.  So they end up in limbo... or Texas.
        fixed_players = []
        msg = '%s: Player %s had to be fixed.'

        for player in self.game.players.distinct():
            if not player.in_limbo(self.game):
                continue
            if player.ticket:
                player.airport = player.ticket.destination
                player.ticket = None
            else:
                player.airport = self.game.start_airport
            player.save()
            logger.info(msg, self.game, player.user.username)
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
        Timer(randint(1, self.max_wait), self._set_throw).start()


messenger = Messenger()
