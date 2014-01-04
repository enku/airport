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
        make_option(
            '--forcequit',
            type='int',
            default=0,
            help='Force a game to quit'
        ),
        make_option(
            '--pause', '-p',
            type='int',
            help='Pause a game (use "0" to pause all active games.'
        ),
        make_option(
            '--resume', '-r',
            type='int',
            help='Resume a game (use "0" to resume all paused games.'
        ),
        make_option(
            '--creategame', '-c',
            type='str',
            help='Create a game with specified host[:airports[:goals].'
        ),
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

        if options['pause'] is not None:
            game_id = options['pause']
            if game_id == 0:
                games = models.Game.objects.filter(
                    state=models.Game.IN_PROGRESS)
            else:
                games = [models.Game.objects.get(pk=game_id)]

            pause_games(games)
            return

        if options['resume'] is not None:
            game_id = options['resume']
            if game_id == 0:
                games = models.Game.objects.filter(state=models.Game.PAUSED)
            else:
                games = [models.Game.objects.get(pk=game_id)]

            resume_games(games)
            return

        if options['creategame'] is not None:
            num_airports = 15
            num_goals = 3
            split = options['creategame'].split(':')
            host_username = split[0]
            player = models.Player.objects.get(user__username=host_username)

            try:
                num_airports = int(split[1])
                num_goals = int(split[2])
            except IndexError:
                pass

            game = models.Game.objects.create_game(
                host=player,
                goals=num_goals,
                airports=num_airports,
                ai_player=True,
            )

            lib.send_message('game_created', game.pk)
            # auto-start the game
            lib.start_game(game)
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


def pause_games(games):
    """Pause all *game* objects if they are in progress.

    Return the number of games affected."""
    num_changed = 0
    for game in games:
        if game.state == game.IN_PROGRESS:
            lib.game_pause(game)
            msg = '{0} paused by administrator.'.format(game)
            models.Message.objects.broadcast(
                msg, game=game, finishers=False, message_type='ERROR')
            lib.send_message('game_paused', game.pk)
            num_changed = num_changed
    return num_changed


def resume_games(games):
    """Pause all *game* objects if they are paused.

    Return the number of games affected."""
    num_changed = 0
    for game in games:
        if game.state == game.PAUSED:
            lib.game_resume(game)
            msg = '{0} resumed by administrator.'.format(game)
            models.Message.objects.broadcast(
                msg, game=game, finishers=False, message_type='ERROR')
            lib.send_message('game_paused', game.pk)
            num_changed = num_changed
    return num_changed
