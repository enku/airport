from logging import getLogger

from django.db import connection
from django.core.management.base import BaseCommand

from airport import lib
from airport import models


logger = getLogger('airport.gameserver')


class Command(BaseCommand):
    """Airport Game Server"""
    def handle(self, *args, **options):
        logger.info('Game Server Started')
        socket_server = start_thread(lib.SocketServer, name='Socket Server')

        games = list(models.Game.open_games().values_list('pk', flat=True))
        connection.close()
        for game_id in games:
            name = 'Game{0}'.format(game_id)
            start_thread(lib.GameThread, name=name, game_id=game_id)

        socket_server.join()


def start_thread(thread_class, **kwargs):
    """Create, start and return the thread."""
    thread = thread_class(**kwargs)
    thread.daemon = True
    thread.start()
    return thread
