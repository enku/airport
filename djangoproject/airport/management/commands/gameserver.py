from logging import getLogger

from django.core.management.base import BaseCommand

from airport.lib.threads import GameThread, messenger, SocketServer
from airport.models import Game


logger = getLogger('airport.gameserver')


class Command(BaseCommand):
    """Airport Game Server"""
    def handle(self, *args, **options):
        logger.info('Game Server Started')
        messenger.start()
        socket_server = start_thread(SocketServer, name='Socket Server')

        for game in Game.open_games():
            start_thread(GameThread, game=game)

        socket_server.join()


def start_thread(thread_class, **kwargs):
    """Create, start and return the Messenger thread."""
    thread = thread_class(**kwargs)
    thread.daemon = True
    thread.start()
    return thread
