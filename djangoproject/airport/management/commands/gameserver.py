from optparse import make_option
from time import sleep

from django.core.management.base import BaseCommand
from django.db import connection

from airport import lib, logger, models


class Command(BaseCommand):

    """Airport Game Server"""
    args = '[--forcequit=game_id]'
    help = 'Airport Game Server'

    option_list = BaseCommand.option_list + (
        make_option(
            '--forcequit',
            type='int',
            default=0,
            help='Force a game to quit',
            metavar='GAMEID',
        ),
        make_option(
            '--pause', '-p',
            type='int',
            help='Pause a game (use "0" to pause all active games.',
            metavar='GAMEID',
        ),
        make_option(
            '--resume', '-r',
            type='int',
            help='Resume a game (use "0" to resume all paused games.',
            metavar='GAMEID',
        ),
        make_option(
            '--creategame', '-c',
            type='str',
            help='Create a game with specified host[:airports[:goals]].',
            metavar='USER[:AIRPORTS[:GOALS]]',
        ),
        make_option(
            '--deletegame', '-d',
            type='int',
            help='Delete a game.  Use with caution!',
            metavar='GAMEID',
        )
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
            pause_games(options['pause'])
            return

        if options['resume'] is not None:
            resume_games(options['resume'])
            return

        if options['creategame'] is not None:
            create_game(*options['creategame'].split(':'))
            return

        if options['deletegame'] is not None:
            delete_game(options['deletegame'])
            return

        logger.info('Game Server Started')
        socket_server = start_thread(lib.SocketServer, name='Socket Server')

        connection.close()
        start_thread(lib.GameThread)

        socket_server.join()


def start_thread(thread_class, **kwargs):
    thread = thread_class(**kwargs)
    thread.daemon = True
    thread.start()
    return thread


def pause_games(game_id):
    """Pause all game objects if they are in progress.

    *game_id* is a game id or "0" for all games.

    Return the set of games affected."""
    games_affected = set()

    if game_id == '0':
        games = models.Game.objects.filter(state=models.Game.IN_PROGRESS)
    else:
        games = models.Game.objects.filter(pk=game_id)

    for game in games:
        if game.state != game.IN_PROGRESS:
            continue
        lib.game_pause(game)
        msg = '{0} paused by administrator.'.format(game)
        models.Message.objects.broadcast(
            msg, game=game, finishers=False, message_type='ERROR')
        lib.send_message('game_paused', game.pk)
        games_affected.add(game)
    return games_affected


def resume_games(game_id):
    """Pause all *game* objects if they are paused.

    *game_id* is a game id or "0" for all games.

    Return the set of games affected."""
    games_affected = set()

    if game_id == 0:
        games = models.Game.objects.filter(state=models.Game.PAUSED)
    else:
        games = models.Game.objects.filter(pk=game_id)

    for game in games:
        if game.state != game.PAUSED:
            continue
        lib.game_resume(game)
        msg = '{0} resumed by administrator.'.format(game)
        models.Message.objects.broadcast(
            msg, game=game, finishers=False, message_type='ERROR')
        lib.send_message('game_paused', game.pk)
        games_affected.add(game)
    return games_affected


def create_game(*args):
    """Create a game.

    args[0]: (required) is the game host's username
    args[1]: (optional) is the number of airports (defaults to 15)
    args[2]: (optional) is the number of goals (defaults to 3)

    Returns the Game object created.
    """
    num_airports = 15
    num_goals = 3

    host_username = args[0]
    player = models.Player.objects.get(user__username=host_username)

    try:
        num_airports = int(args[1])
        num_goals = int(args[2])
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
    return game


def delete_game(game_id):
    """Delete the game assicated with *game_id*.

    Return the deleted game

    Pro-tip: We don't really delete games.  We just end them.
    """
    game = models.Game.objects.get(pk=game_id)
    game.end()
    return game
