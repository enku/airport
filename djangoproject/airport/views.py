"""
Django views for the airport app
"""
import datetime
import json

from django import get_version
from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import (get_object_or_404, redirect, render,
                              render_to_response)
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from airport import forms, lib, models, VERSION
from airport.conf import settings


@login_required
def main(request):
    """Main view"""
    player = request.user.player
    game = player.current_game

    if game and game.state == game.NOT_STARTED and game.host != player:
        msg = 'Waiting for {0} to start the game.'
        msg = msg.format(game.host.user.username)
        models.Message.objects.send(player, msg)
    websocket_url = get_websocket_url(request)
    context = {
        'game': game,
        'player': player,
        'websocket_url': websocket_url,
    }
    return render(request, 'airport/main.html', context)


@login_required
def info(request):
    """Used ajax called to be used by the main() view.

    Returns basically all the info needed by main() but as as json
    dictionary.
    """
    user = request.user
    player = user.player
    game = player.current_game

    if not game:
        return games_info(request)
    if game.state == game.NOT_STARTED:
        return games_info(request)
    if game.state == game.GAME_OVER or player.finished(game):
        return json_redirect('%s?id=%s' % (reverse(game_summary), game.id))
    now = game.time
    flight_purchased = None

    if request.method == 'POST':
        if 'selected' in request.POST:
            flight_id = int(request.POST['selected'])
            flight = get_object_or_404(models.Flight, game=game, pk=flight_id)
            flight_purchased = purchase_flight(player, flight, now)

    if flight_purchased:
        lib.send_message('throw_wrench', game.pk)
        game = models.Game.objects.get(pk=game.pk)
        now = game.time
    player_info = player.info(game, now)
    return json_response(player_info)


def purchase_flight(player, flight, game_time):
    """Make player attempt to purchase flight.

    If flight is available for purchase, Return it. Else returns None.

    Also sends an appropriate message to the player if the flight could not be
    purchased.
    """
    try:
        player.purchase_flight(flight, game_time)
    except models.Flight.AlreadyDeparted:
        msg = 'Flight {0} has already left.'.format(flight.number)
        models.Message.objects.send(player, msg, message_type='ERROR')
        return None
    except models.Flight.Full:
        msg = 'Flight {0} is full.'.format(flight.number)
        models.Message.objects.send(player, msg, message_type='ERROR')
        return None
    return flight


@require_http_methods(['POST'])
@login_required
def pause_game(request):
    """Pause/Resume game"""
    player = request.user.player
    game = player.current_game

    if not game or game.host != player:
        return info(request)

    if game.state == game.PAUSED:
        player_info = lib.game_resume(game)
    elif game.state == game.IN_PROGRESS:
        player_info = lib.game_pause(game)

    lib.send_message('game_paused', game.pk)
    return json_response(player_info)


@require_http_methods(['POST'])
@login_required
def rage_quit(request):
    """Bail out of the game because you are a big wuss"""
    player = request.user.player
    game = player.current_game

    if not game:
        return info(request)
    # If we call player.info() *after* we've removed them from the game, it
    # gets confused because the player is not in the game and it tries to add
    # them.  And then if they were the only player in the game it can't add
    # them because the game is over (because there are no players).  Anyway we
    # don't want this either way.  Call player.info() before removing them from
    # the game.
    game.remove_player(player)
    if game.state != game.GAME_OVER:
        models.Message.objects.send(player, 'You have quit %s. Wuss!' % game)
    lib.send_message('player_left_game', (player.pk, game.pk))
    return info(request)


@login_required
def messages(request):
    """View to return user's current messages"""
    last_message = int(request.GET.get('last', 0))
    old = 'old' in request.GET
    response = HttpResponse()
    response['Cache-Control'] = 'no-cache'
    _messages = models.Message.objects.get_messages(request, last_message,
                                                    old=old)
    if not _messages:
        response.status_code = 304
        response.content = ''
        return response

    response['Content-Type'] = 'text/html'
    content = render_to_string('airport/messages.html',
                               {'messages': _messages, 'old': old})
    response.content = content
    return response


@login_required
def games_info(request):
    """Just another json view"""
    player = request.user.player
    game = player.current_game

    # if user is in an open game and it has started, redirect to that game
    if (game and game.state in (game.IN_PROGRESS, game.PAUSED)
            and request.user.player.finished(game)):
        return json_redirect(reverse(main))

    data = player.game_info()
    data['games'] = models.Game.games_info()
    return json_response(data)


@require_http_methods(['POST'])
@login_required
def games_create(request):
    """Create a game, or if the user is currently in a non-closed game,
    send a message saying they can't create a game(yet).  Finally, redirect
    to the games view
    """
    user = request.user
    player = user.player

    form = forms.CreateGameForm(request.POST)
    if not form.is_valid():
        text = 'Error creating game.'
        text = text.format(form.errors.values())
        models.Message.objects.send(player, text)
        return games_info(request)

    data = form.cleaned_data
    num_goals = data['goals']
    num_airports = data['airports']
    ai_player = data['ai_player']

    games = models.Game.objects.exclude(state=models.Game.GAME_OVER)
    games = games.filter(players=player)
    winners = models.Player.objects.winners
    if games.exists() and not all([player in winners(i) for i in games]):
        m = 'Cannot create a game since you are already playing an open game.'
        models.Message.objects.send(player, m)
    else:
        game = models.Game.objects.create_game(
            host=player,
            goals=num_goals,
            airports=num_airports,
            ai_player=ai_player,
        )
        lib.send_message('game_created', game.pk)

    return games_info(request)


@login_required
@require_http_methods(['POST'])
def games_join(request):
    """Join a game.  Game must exist and have not ended (you can join a
    game that is in progress
    """
    player = request.user.player

    game_id = request.POST.get('id', None)
    game = get_object_or_404(models.Game, id=game_id)
    if game.state == game.GAME_OVER:
        msg = 'Could not join you to {0} because it is over.'
        msg = msg.format(game)
        models.Message.objects.send(player, msg)
    elif player.is_playing(game):
        if player in models.Player.objects.winners(game):
            msg = 'You have already finished {0}.'
            msg = msg.format(game)
            models.Message.objects.send(player, msg)
        else:
            if game.state > game.GAME_OVER:
                return json_redirect(reverse(main))
            else:
                msg = 'You have already joined {0}.'
                msg = msg.format(game)
                models.Message.objects.send(player, msg)
    else:
        game.add_player(player)
        msg = '{0} has joined {1}.'.format(player, game)
        models.Message.objects.announce(player, msg, game, 'PLAYERACTION')
        lib.send_message('player_joined_game', (player.pk, game.pk))

    return info(request)


@require_http_methods(['POST'])
@login_required
def games_start(request):
    """Start the game hosted by the user.

    If user doesn't host a game this will 404.
    """
    player = request.user.player
    game = get_object_or_404(
        models.Game,
        host=player,
        state=models.Game.NOT_STARTED
    )
    lib.start_game(game)
    return json_response(game.info())


@login_required
def games_stats(request):
    """Return user stats on game"""
    player = request.user.player
    games = player.games

    cxt = {}
    cxt['user'] = request.user
    cxt['game_count'] = games.count()
    cxt['won_count'] = models.Game.objects.won_by(player).count()
    cxt['goal_count'] = player.goals.count()
    cxt['ticket_count'] = player.tickets.count()
    cxt['flight_hours'] = sum((i.flight.flight_time
                               for i in player.tickets)) / 60.0

    cxt['total_time'] = datetime.timedelta(seconds=0)
    for game in games.distinct():
        last_goal = game.last_goal()
        my_time = models.Achievement.objects.get(game=game, goal=last_goal,
                                                 player=player).timestamp
        if not my_time:
            continue
        cxt['total_time'] = cxt['total_time'] + (my_time - game.creation_time)
    cxt['total_time'] = cxt['total_time']

    if cxt['game_count']:
        cxt['avg_time'] = cxt['total_time'].total_seconds() / cxt['game_count']
        cxt['flight_hours_per_game'] = cxt['flight_hours'] / cxt['game_count']
        cxt['goals_per_game'] = cxt['goal_count'] / cxt['game_count']
    else:
        cxt['avg_time'] = 0.0
        cxt['flight_hours_per_game'] = 0.0
        cxt['game_count'] = 0.0

    if cxt['goal_count']:
        cxt['tix_per_goal'] = cxt['ticket_count'] / cxt['goal_count']
    else:
        cxt['tix_per_goal'] = 0.0

    # we really want hours though
    cxt['avg_time'] = cxt['avg_time'] / 3600.0
    cxt['total_time'] = cxt['total_time'].total_seconds() / 3600.0

    prior_games = games.exclude(state=-1).distinct()
    prior_games = prior_games.values_list('id', 'timestamp')
    prior_games = prior_games.order_by('-id')
    prior_games = prior_games[:settings.GAME_HISTORY_COUNT]
    prior_games = list(prior_games)

    # we may not yet be finished with the last game, if that's the case
    # then don't show it
    if prior_games:
        last_game = models.Game.objects.get(id=prior_games[0][0])
        if not player.finished(last_game):
            prior_games.pop(0)
    cxt['prior_games'] = prior_games

    return render_to_response('airport/games_stats.html', cxt)


@login_required
def game_summary(request):
    """Show summary for a particular game, request.user must have actually
    played the game to utilize this view"""
    game_id = request.GET.get('id', None)
    game = get_object_or_404(models.Game, id=int(game_id))

    username = request.GET.get('player', None)
    if username:
        player = get_object_or_404(
            models.Player, user__username=username)
    else:
        player = request.user.player

    if not player.is_playing(game):
        return redirect(main)

    goals = list(models.Goal.objects.filter(game=game).order_by('order'))
    tickets = models.Purchase.objects.filter(
        player=player, game=game).order_by('creation_time')

    current_goal = 0
    for ticket in tickets:
        ticket.goal = False
        try:
            if ticket.flight.destination.city == goals[current_goal].city:
                ticket.goal = True
                current_goal = current_goal + 1
        except IndexError:
            pass

    placed = game.place(player)

    context = {}
    context['player'] = player
    context['tickets'] = tickets
    context['placed'] = placed
    context['game'] = game
    context['goals'] = goals
    context['num_airports'] = game.airports.distinct().count()
    context['players'] = game.players.exclude(id=player.id).distinct()
    context['map_latitude'] = settings.MAP_INITIAL_LATITUDE
    context['map_longitude'] = settings.MAP_INITIAL_LONGITUDE
    context['map_zoom'] = settings.MAP_INITIAL_ZOOM

    return render(request, 'airport/game_summary.html', context)


def crash(_request):
    """Case the app to crash"""
    raise Exception('Crash forced!')


def city_image(request, city_name):
    """Redirect to the url of the image for a city, or the default if it
    has None"""
    try:
        city = models.City.objects.get(name=city_name)
    except models.City.DoesNotExist:
        return redirect(settings.EXTERNALS['background_image'])

    if city.image:
        return redirect(city.image)
    return redirect(settings.EXTERNALS['background_image'])


def json_redirect(url):
    """Return a simple json dictionary with a redirect key and url value"""
    return HttpResponse(
        json.dumps({'redirect': url}),
        content_type='application/json'
    )


def json_response(data):
    """Return data as a json-formatted HttpResponse."""
    json_str = json.dumps(data)
    return HttpResponse(json_str, content_type='application/json')


def register(request):
    """The view that handles the actual registration form"""

    context = dict()
    context['form'] = UserCreationForm()

    if request.method == "POST":
        context['form'] = form = UserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            try:
                models.Player.objects.get(user__username=username)
                context['error'] = 'User {0} already exists.'.format(username)
            except models.Player.DoesNotExist:
                create_user(username, password)
                django_messages.add_message(
                    request, django_messages.INFO,
                    'Account activated. Please sign in.')
                return redirect(main)
        else:
            context['error'] = form._errors

    context['users'] = models.Player.objects.all()
    return render(request, 'registration/register.html', context)


def about(request):
    """Classic /about view"""
    repo_url = settings.AIRPORT_REPO_URL
    django_version = get_version()
    user_agent = request.META['HTTP_USER_AGENT']
    context = {
        'version': VERSION,
        'repo_url': repo_url,
        'django_version': django_version,
        'user_agent': user_agent
    }

    return render(request, 'airport/about.html', context)


def create_user(username, password):
    """Create a (regular) user account"""

    new_user = User()
    new_user.username = username
    new_user.set_password(password)
    new_user.is_active = True
    new_user.save()

    player = models.Player()
    player.user = new_user
    player.save()

    return new_user


def get_websocket_url(request):
    http_host = request.META.get('HTTP_HOST', 'localhost')
    if ':' in http_host:
        http_host = http_host.split(':', 1)[0]
    return 'ws://{0}:{1}/'.format(http_host, settings.WEBSOCKET_PORT)
