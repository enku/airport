from logging import getLogger

from django.core.management.base import BaseCommand

from airport import lib
from airport import models


logger = getLogger('airport.gameserver')


class Command(BaseCommand):
    """Airport Game Server"""
    def handle(self, *args, **options):
        logger.info('Game Server Started')
        lib.messenger.start()
        socket_server = start_thread(lib.SocketServer,
                                     name='Socket Server')

        for game in models.Game.open_games():
            start_thread(lib.GameThread, game=game)

        socket_server.join()


def start_thread(thread_class, **kwargs):
    """Create, start and return the Messenger thread."""
    thread = thread_class(**kwargs)
    thread.daemon = True
    thread.start()
    return thread
