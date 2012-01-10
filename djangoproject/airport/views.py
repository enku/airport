"""
Django views for the airport app
"""
import datetime
import json
import random

from django import get_version
from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.humanize.templatetags.humanize import naturalday
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import (
    render, render_to_response, get_object_or_404, redirect)
from django.template.defaultfilters import date, escape
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from airport import VERSION
from airport.models import (
        Achievement,
        AirportMaster,
        Flight,
        Game,
        Goal,
        Message,
        Purchase,
        UserProfile)

from airport.monkeywrench import MonkeyWrenchFactory

DTHANDLER = lambda obj: (obj.isoformat()
        if isinstance(obj, datetime.datetime) else None)
MW_PROBABILITY = getattr(settings, 'MONKEYWRENCH_PROBABILITY', 20)
MWF = MonkeyWrenchFactory()
GAME_HISTORY_COUNT = 15

@login_required
def home(request):
    """Main view"""
    profile = request.user.profile
    game = profile.current_game

    if not game:
        return redirect(games_home)
    if game.state == game.GAME_OVER:
        Message.send(profile, '%s is over' % game)
        return redirect(games_home)
    if profile in game.finishers():
        return redirect(games_home)
    if game.state == game.NOT_STARTED:
        if profile == game.host:
            game.begin()
            Message.announce(request.user, '%s has started %s' % (request.user,
                game))
        else:
            Message.send(profile, 'Waiting for %s to start the game' %
                    game.host.user.username)
            return redirect(games_home)
    context = {
        'game': game,
        'profile': profile
    }
    return render(request, 'airport/home.html', context)

@login_required
def info(request):
    """Used ajax called to be used by the home() view.
    Returns basically all the info needed by home() but as as json
    dictionary"""
    user = request.user
    profile = user.profile

    game = profile.current_game
    if not game:
        return json_redirect(reverse(games_home))
    if game.state == game.GAME_OVER or profile in game.finishers():
        return json_redirect(reverse(game_summary, args=[str(game.id)]))
    now, airport, ticket = game.update(profile)

    calc_mwp = game.players.distinct().count() * MW_PROBABILITY
    if random.randint(1, calc_mwp) == calc_mwp:
        MWF.create(game).throw()

    if request.method == 'POST':
        if 'selected' in request.POST:
            flight_no = int(request.POST['selected'])
            flight = get_object_or_404(Flight, game=game, number=flight_no)

            # try to purchase the flight
            try:
                ticket = profile.purchase_flight(flight, now)
            except Flight.AlreadyDeparted:
                Message.send(profile,
                        'Flight %s has already left' % flight.number)
        return redirect(info)

    percentage = 100
    next_flights = []
    if ticket and ticket.in_flight(now):
        next_flights = ticket.destination.next_flights(game, now)
        percentage = ((now - ticket.depart_time).total_seconds()
                / 60.0
                / ticket.flight_time
                * 100)
    elif airport:
        next_flights = airport.next_flights(game, now)

    last_message = Message.get_latest(request.user)

    if ticket:
        in_flight = ticket.in_flight(now)
    else:
        in_flight = False

    if ticket and not in_flight and ticket.destination == ticket.origin:
        # special case when e.g. flight diverted back to origin
        ticket = None

    if not request.session.get('in_flight', False) and in_flight:
        Message.announce(user, '%s has left %s' % (user,
            ticket.origin), game, message_type='PLAYERACTION')
        Purchase.objects.get_or_create(profile=profile, game=game,
                flight=ticket)

    if (request.session.get('in_flight', False)
            and not in_flight
            and not profile in game.winners()):
        notify = 'You have arrived at %s' % airport
    else:
        notify = None

    request.session['in_flight'] = in_flight

    nf_list = []
    for next_flight in next_flights:
        nf_dict = next_flight.to_dict(now)
        nf_dict['buyable'] = next_flight.buyable(profile, now)
        nf_list.append(nf_dict)

    goal_list = []
    for goal in Goal.objects.filter(game=game):
        achieved = goal.achievers.filter(id=profile.id,
                achievement__timestamp__isnull=False).exists()
        goal_list.append([goal.city.name, achieved])

    stats = game.stats()

    json_str = json.dumps(
        {
            'time': date(now, 'P'),
            'airport': airport.name if airport else ticket.origin,
            'ticket': None if not ticket else ticket.to_dict(now),
            'next_flights': nf_list,
            'message_id': last_message.id if last_message else None,
            'in_flight': in_flight,
            'percentage': percentage,
            'goals': goal_list,
            'stats': stats,
            'notify': notify,
            'player': user.username
        },
        default=DTHANDLER
    )
    return HttpResponse(json_str, mimetype='application/json')

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
        'airport_count': airport_count
    }

    return render(request, 'airport/games.html', context)

@login_required
def games_info(request):
    """Just another json view"""

    profile = request.user.profile
    game = profile.current_game
    state = profile.current_state

    # if user is in an open game and it has started, redirect to that game
    if (game and game.state == game.IN_PROGRESS
            and request.user.profile not in game.winners()):
        return json_redirect(reverse(home))

    # active games
    games = Game.objects.annotate(Count('players', distinct=True))
    games = games.annotate(Count('airports', distinct=True))
    games = games.annotate(Count('goals', distinct=True))
    games = games.exclude(state=0)
    games = games.order_by('creation_time')
    games = games.values_list(
        'id',
        'players__count',
        'host__user__username',
        'goals__count',
        'airports__count',
        'state',
        'creation_time')
    glist = []
    for game in games:
        glist.append(dict(
            id = game[0],
            players = game[1],
            host = escape(game[2]),
            goals = game[3],
            airports = game[4],
            status = ['New', 'Finished', 'Started'][game[5] + 1],
            created = naturaltime(game[6])))

    current_game = (Game.objects
            .exclude(state=0)
            .filter(players=request.user.profile)
            .distinct()
            .order_by('-timestamp'))

    if current_game.exists():
        finished_current = request.user.profile in current_game[0].winners()
        current_game = current_game[0].id
    else:
        current_game = None
        finished_current = False

    data = {
            'games': glist,
            'current_game': current_game,
            'current_state': state,
            'finished_current': finished_current
    }
    return HttpResponse(json.dumps(data), mimetype='application/json')

@require_http_methods(['POST'])
@login_required
def games_create(request):
    """Create a game, or if the user is currently in a non-closed game,
    send a message saying they can't create a game(yet).  Finally, redirect
    to the games view
    """
    user = request.user
    profile = user.profile

    try:
        num_goals = int(request.POST['goals'])
        num_airports = int(request.POST['airports'])
    except KeyError:
        text = ('Error creating game.  Incorrect params: '
                'goals: %s, airports: %s' % (request.POST.get('goals'),
                    request.POST.get('params')))
        Message.send(profile, text)
        return redirect(games_home)

    games = Game.objects.exclude(state=Game.GAME_OVER)
    games = games.filter(players=profile)
    if games.exists() and not all([profile in i.winners() for i in games]):
        Message.send(profile, ('Cannot create a game since you are '
            'already playing an open game.'))
    else:
        game = Game.create(profile, num_goals, num_airports)
        game.save()

    return games_info(request)

@login_required
def games_join(request, game_id):
    """Join a game.  Game must exist and have not ended (you can join a
    game that is in progress
    """
    profile = request.user.profile

    game = get_object_or_404(Game, id=game_id)
    if game.state == game.GAME_OVER:
        Message.send(profile, 'Could not join you to %s because it is over'
                % game)
    elif profile.is_playing(game):
        if profile in game.winners():
            Message.send(profile, 'You have already finished %s' % game)
        else:
            Message.send(profile, 'You have already joined %s' % game)
    else:
        game.add_player(profile)

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
    cxt['flight_hours_per_game'] = (cxt['flight_hours'] /
        cxt['game_count'] if cxt['game_count'] else 0)

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
    prior_games = prior_games[:GAME_HISTORY_COUNT]
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
def game_summary(request, game_id):
    """Show summary for a particular game, request.user must have actually
    played the game to utilize this view"""
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

    return render(request, 'airport/game_summary.html', context)

def crash(_request):
    """Case the app to crash"""
    raise Exception('Crash forced!')

def json_redirect(url):
    """Return a simple json dictionary with a redirect key and url value"""
    return HttpResponse(
        json.dumps({'redirect': url}),
        mimetype='application/json'
    )

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
                context['error'] = 'User "%s" already exists.' % username
            except UserProfile.DoesNotExist:
                create_user(username, password)
                django_messages.add_message(request, django_messages.INFO,
                    'Account activated. Please sign in.')
                return redirect(home)
        else:
            context['error'] = form._errors

    context['users'] = UserProfile.objects.all()
    return render(request, 'registration/register.html', context)

def about(request):
    """Classic /about view"""
    repo_url = getattr(settings, 'AIRPORT_REPO_URL', None)
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

    userprofile = UserProfile()
    userprofile.user = new_user
    userprofile.save()

    return new_user

def timedelta_to_hrs(td_object):
    """Return timedelta object as hours"""
    return td_object.total_seconds() / 3600.0

# TODO: borrowed from Django development version, remove when released
def naturaltime(value, arg=None):
    """
    For date and time values shows how many seconds, minutes or hours ago compared to
    current timestamp returns representing string. Otherwise, returns a string
    formatted according to settings.DATE_FORMAT
    """
    try:
        value = datetime.datetime(value.year, value.month, value.day,
                value.hour, value.minute, value.second)
    except AttributeError:
        return value
    except ValueError:
        return value

    delta = datetime.datetime.now() - value
    if delta.days != 0:
        value = datetime.date(value.year, value.month, value.day)
        return naturalday(value, arg)
    elif delta.seconds == 0:
        return (u'now')
    elif delta.seconds < 60:
        return (u"%s seconds ago" % (delta.seconds))
    elif delta.seconds / 60 < 2:
        return (r'a minute ago')
    elif delta.seconds / 60 < 60:
        return (u"%s minutes ago" % (delta.seconds/60))
    elif delta.seconds / 60 / 60 < 2:
        return (u'an hour ago')
    elif delta.seconds / 60 / 60 < 24:
        return (u"%s hours ago" % (delta.seconds/60/60))
    return naturalday(value, arg)
