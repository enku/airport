from logging import getLogger
from optparse import make_option
from time import sleep

from django.db import connection
from django.core.management.base import BaseCommand

from airport import lib
from airport import models


logger = getLogger('airport.gameserver')


class Command(BaseCommand):

    """Airport Game Server"""
    args = '[--forcequit=game_id]'
    help = 'Airport Game Server'

    option_list = BaseCommand.option_list + (
        make_option('--forcequit',
                    type='int',
                    default=0,
                    help='Force a game to quit'),
    )

    def handle(self, *args, **options):
        if options['forcequit']:
            game = models.Game.objects.get(pk=options['forcequit'])
            logger.info('Shutting down {0}.'.format(game))
            msg = '{0} is being forced to quit.'.format(game)
            models.Message.objects.broadcast(
                msg, game=game, finishers=True, message_type='ERROR')
            # give the broadcast a few seconds to get received
            sleep(4.0)
            game.end()
            lib.send_message('game_ended', game.pk)
            return

        logger.info('Game Server Started')
        socket_server = start_thread(lib.SocketServer, name='Socket Server')

        games = list(models.Game.open_games().values_list('pk', flat=True))
        connection.close()
        for game_id in games:
            name = 'Game{0}'.format(game_id)
            start_thread(lib.GameThread, name=name, game_id=game_id)

        socket_server.join()


def start_thread(thread_class, **kwargs):
    thread = thread_class(**kwargs)
    thread.daemon = True
    thread.start()
    return thread
