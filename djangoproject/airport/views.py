"""
Django views for the airport app
"""
from __future__ import unicode_literals

import datetime
import json

from django import get_version
from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import (
    render, render_to_response, get_object_or_404, redirect)
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

import airport
from airport.conf import settings
from airport.context_processors import externals
from airport import forms
from airport.lib import websocket
from airport.models import (
    Achievement,
    AirportMaster,
    City,
    Flight,
    Game,
    Goal,
    Message,
    Purchase,
    UserProfile)

send = Message.send
announce = Message.announce


@login_required
def home(request):
    """Main view"""
    profile = request.user.profile
    game = profile.current_game
    context = {}

    if not game:
        return redirect(games_home)
    if game.state == game.GAME_OVER:
        return redirect(games_home)
    if profile in game.finishers():
        return redirect(games_home)
    if game.state == game.NOT_STARTED:
        if profile == game.host:
            airport.start_game(game)
        else:
            msg = 'Waiting for {0} to start the game.'
            msg = msg.format(game.host.user.username)
            send(profile, msg)
            return redirect(games_home)
    websocket_url = get_websocket_url(request)
    context['game'] = game
    context['profile'] = profile
    context['websocket_url'] = websocket_url
    return render(request, 'airport/home.html', context)


@login_required
def info(request):
    """Used ajax called to be used by the home() view.

    Returns basically all the info needed by home() but as as json
    dictionary.
    """
    user = request.user
    profile = user.profile
    game = profile.current_game
    if not game:
        return json_redirect(reverse(games_home))
    if game.state == game.GAME_OVER or profile in game.finishers():
        return json_redirect('%s?id=%s' % (reverse(game_summary), game.id))
    now = game.time
    flight_purchased = None

    if request.method == 'POST':
        if 'selected' in request.POST:
            flight_id = int(request.POST['selected'])
            flight = get_object_or_404(Flight, game=game, pk=flight_id)
            flight_purchased = purchase_flight(profile, flight, now)

    if flight_purchased:
        websocket.IPCHandler.send_message('throw_wrench', game.pk)
        game = Game.objects.get(pk=game.pk)
        now = game.time
    player_info = profile.info(game, now)
    return json_response(player_info)


def purchase_flight(player, flight, game_time):
    """Make player attempt to purchase flight.

    If flight is available for purchase, Return it. Else returns None.

    Also sends an appropriate message to the player if the flight could not be
    purchased.
    """
    try:
        player.purchase_flight(flight, game_time)
    except Flight.AlreadyDeparted:
        msg = 'Flight {0} has already left.'.format(flight.number)
        send(player, msg, message_type='ERROR')
        return None
    except Flight.Full:
        msg = 'Flight {0} is full.'.format(flight.number)
        send(player, msg, message_type='ERROR')
        return None
    return flight


@require_http_methods(['POST'])
@login_required
def pause_game(request):
    """Pause/Resume game"""
    game_id = request.GET.get('id', None)
    game = get_object_or_404(Game, pk=game_id)
    player = request.user.profile

    if player != game.host:
        # only the host can pause/resume the game
        return player.info(game)

    if game.state == game.PAUSED:
        player_info = airport.game_resume(game)
    elif game.state == game.IN_PROGRESS:
        player_info = airport.ame_pause(game)

    websocket.IPCHandler.send_message('game_paused', game.pk)
    return json_response(player_info)


@require_http_methods(['POST'])
@login_required
def rage_quit(request):
    """Bail out of the game because you are a big wuss"""
    game_id = request.GET.get('id', None)
    game = get_object_or_404(Game, id=game_id)
    player = request.user.profile

    # If we call player.info() *after* we've removed them from the game, it
    # gets confused because the player is not in the game and it tries to add
    # them.  And then if they were the only player in the game it can't add
    # them because the game is over (because there are no players).  Anyway we
    # don't want this either way.  Call player.info() before removing them from
    # the game.
    game.remove_player(player)
    send(player, 'You have quit %s. Wuss!' % game)
    websocket.IPCHandler.send_message('player_left_game', (player.pk, game.pk))
    return json_redirect(reverse(games_home))


@login_required
def messages(request):
    """View to return user's current messages"""
    last_message = int(request.GET.get('last', 0))
    old = 'old' in request.GET
    response = HttpResponse()
    response['Cache-Control'] = 'no-cache'
    _messages = Message.get_messages(request, last_message, old=old)
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
def games_home(request):
    """Main games view"""
    profile = request.user.profile
    open_game = profile.current_game

    if open_game and (open_game.state == open_game.GAME_OVER or profile in
                      open_game.winners()):
        open_game = None

    airport_count = AirportMaster.objects.all().count()

    context = {
        'user': request.user.username,
        'open_game': open_game,
        'airport_count': airport_count,
        'websocket_url': 'ws://{0}:{1}/'.format(
            'localhost', settings.WEBSOCKET_PORT),
    }

    return render(request, 'airport/games.html', context)


@login_required
def games_info(request):
    """Just another json view"""
    profile = request.user.profile
    game = profile.current_game

    # if user is in an open game and it has started, redirect to that game
    if (game and game.state in (game.IN_PROGRESS, game.PAUSED)
            and request.user.profile not in game.finishers()):
        return json_redirect(reverse(home))

    data = profile.game_info()
    data['games'] = Game.games_info()
    return json_response(data)


@require_http_methods(['POST'])
@login_required
def games_create(request):
    """Create a game, or if the user is currently in a non-closed game,
    send a message saying they can't create a game(yet).  Finally, redirect
    to the games view
    """
    user = request.user
    profile = user.profile

    form = forms.CreateGameForm(request.POST)
    if not form.is_valid():
        text = 'Error creating game: {0}'
        text = text.format(form.errors)
        send(profile, text)
        return redirect(games_home)

    data = form.cleaned_data
    num_goals = data['goals']
    num_airports = data['airports']
    ai_player = data['ai_player']

    games = Game.objects.exclude(state=Game.GAME_OVER)
    games = games.filter(players=profile)
    if games.exists() and not all([profile in i.winners() for i in games]):
        m = 'Cannot create a game since you are already playing an open game.'
        send(profile, m)
    else:
        game = Game.objects.create_game(
            host=profile,
            goals=num_goals,
            airports=num_airports,
            ai_player=ai_player,
        )
        websocket.IPCHandler.send_message('game_created', game.pk)

    return games_info(request)


@login_required
def games_join(request):
    """Join a game.  Game must exist and have not ended (you can join a
    game that is in progress
    """
    profile = request.user.profile

    game_id = request.GET.get('id', None)
    game = get_object_or_404(Game, id=game_id)
    if game.state == game.GAME_OVER:
        msg = 'Could not join you to {0} because it is over.'
        msg = msg.format(game)
        send(profile, msg)
    elif profile.is_playing(game):
        if profile in game.winners():
            msg = 'You have already finished {0}.'
            msg = msg.format(game)
            send(profile, msg)
        else:
            msg = 'You have already joined {0}.'
            msg.format(game)
            send(profile, msg)
    else:
        game.add_player(profile)
        msg = '{player.user.username} has joined {game}.'
        msg = msg.format(player=profile, game=game)
        announce(profile, msg, game, 'PLAYERACTION')
        websocket.IPCHandler.send_message('player_joined_game',
                                          (profile.pk, game.pk))

    return games_info(request)


@login_required
def games_stats(request):
    """Return user stats on game"""
    profile = request.user.profile
    games = profile.games

    cxt = {}
    cxt['user'] = request.user
    cxt['game_count'] = games.count()
    cxt['won_count'] = profile.games_won.count()
    cxt['goal_count'] = profile.goals.count()
    cxt['goals_per_game'] = (
        1.0 * cxt['goal_count'] / cxt['game_count']
        if cxt['game_count']
        else 0)
    cxt['ticket_count'] = profile.tickets.count()
    cxt['tix_per_goal'] = (1.0 * cxt['ticket_count'] /
                           cxt['goal_count'] if cxt['goal_count'] else 0)
    cxt['flight_hours'] = sum((i.flight.flight_time
                               for i in profile.tickets)) / 60.0
    cxt['flight_hours_per_game'] = (
        cxt['flight_hours'] / cxt['game_count'] if cxt['game_count'] else 0)

    # average game time
    cxt['total_time'] = datetime.timedelta(seconds=0)
    for game in games.distinct():
        last_goal = game.last_goal()
        my_time = Achievement.objects.get(game=game, goal=last_goal,
                                          profile=profile).timestamp
        if not my_time:
            continue
        cxt['total_time'] = (cxt['total_time']
                             + (my_time - game.creation_time))
    cxt['total_time'] = cxt['total_time']

    cxt['avg_time'] = (
        1.0 * cxt['total_time'].total_seconds() / cxt['game_count']
        if cxt['game_count']
        else 0)
    # we really want hours though
    cxt['avg_time'] = cxt['avg_time'] / 3600.0
    cxt['total_time'] = timedelta_to_hrs(cxt['total_time'])

    prior_games = games.exclude(state=-1).distinct()
    prior_games = prior_games.values_list('id', 'timestamp')
    prior_games = prior_games.order_by('-id')
    prior_games = prior_games[:settings.GAME_HISTORY_COUNT]
    prior_games = list(prior_games)

    # we may not yet be finished with the last game, if that's the case
    # then don't show it
    if prior_games:
        last_game = Game.objects.get(id=prior_games[0][0])
        if last_game.place(profile) == 0:
            prior_games.pop(0)

    cxt['prior_games'] = prior_games

    return render_to_response('airport/games_stats.html', cxt)


@login_required
def game_summary(request):
    """Show summary for a particular game, request.user must have actually
    played the game to utilize this view"""
    game_id = request.GET.get('id', None)
    game = get_object_or_404(Game, id=int(game_id))

    username = request.GET.get('player', None)
    if username:
        profile = get_object_or_404(UserProfile, user__username=username)
    else:
        profile = request.user.profile

    if not profile.is_playing(game):
        return redirect(games_home)

    goals = list(Goal.objects.filter(game=game).order_by('order'))
    tickets = Purchase.objects.filter(profile=profile,
                                      game=game).order_by('creation_time')

    current_goal = 0
    for ticket in tickets:
        ticket.goal = False
        try:
            if ticket.flight.destination.city == goals[current_goal].city:
                ticket.goal = True
                current_goal = current_goal + 1
        except IndexError:
            pass

    placed = game.place(profile)

    context = {}
    context['profile'] = profile
    context['tickets'] = tickets
    context['placed'] = placed
    context['game'] = game
    context['goals'] = goals
    context['num_airports'] = game.airports.distinct().count()
    context['players'] = game.players.exclude(id=profile.id).distinct()
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
        city = City.objects.get(name=city_name)
    except City.DoesNotExist:
        return redirect(externals(request)['background_image'])

    if city.image:
        return redirect(city.image)
    return redirect(externals(request)['background_image'])


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
                UserProfile.objects.get(user__username=username)
                context['error'] = 'User {user} already exists.'.format(
                    user=username)
            except UserProfile.DoesNotExist:
                create_user(username, password)
                django_messages.add_message(
                    request, django_messages.INFO,
                    'Account activated. Please sign in.')
                return redirect(home)
        else:
            context['error'] = form._errors

    context['users'] = UserProfile.objects.all()
    return render(request, 'registration/register.html', context)


def about(request):
    """Classic /about view"""
    repo_url = settings.AIRPORT_REPO_URL
    django_version = get_version()
    user_agent = request.META['HTTP_USER_AGENT']
    context = {
        'version': airport.VERSION,
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

    userprofile = UserProfile()
    userprofile.user = new_user
    userprofile.save()

    return new_user


def timedelta_to_hrs(td_object):
    """Return timedelta object as hours"""
    return td_object.total_seconds() / 3600.0


def get_websocket_url(request):
    http_host = request.META.get('HTTP_HOST', 'localhost')
    if ':' in http_host:
        http_host = http_host.split(':', 1)[0]
    return 'ws://{0}:{1}/'.format(http_host, settings.WEBSOCKET_PORT)
