"""
Django views for the airport app
"""
import datetime
import json
import random

from django import get_version
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.template.defaultfilters import date, escape
from django.views.decorators.http import require_http_methods

from airport import VERSION
from airport.models import (
        Achiever,
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

@login_required
def home(request):
    """Main view"""
    return render_to_response('airport/home.html', {}, RequestContext(request))

@login_required
def info(request):
    """Used ajax called to be used by the home() view.
    Returns basically all the info needed by home() but as as json
    dictionary"""
    user = request.user
    profile = user.profile

    game = profile.current_game
    if not game:
        Message.send(profile,
            'The game has either ended or not yet started')
        return json_redirect(reverse(games_home))
    now, airport, ticket = game.update(profile)

    if random.randint(1, MW_PROBABILITY) == MW_PROBABILITY:
        MWF.create(game).throw()

    if request.method == 'POST':
        if 'selected' in request.POST:
            flight_no = int(request.POST['selected'])
            flight = get_object_or_404(Flight, game=game, number=flight_no)

            # try to purchase the flight
            try:
                ticket = profile.purchase_flight(flight, now)
            except Flight.AlreadyDeparted:
                Message.send(profile, 'Flight %s has already left' % flight.number)
        return redirect(info)

    messages = Message.get_messages(request)

    if ticket:
        in_flight = ticket.in_flight(now)
    else:
        in_flight = False

    if not request.session.get('in_flight', False) and in_flight:
        Message.announce(user, '%s has left %s' % (user,
            ticket.origin))
        Purchase.objects.get_or_create(profile=profile, game=game,
                flight=ticket)
    request.session['in_flight'] = in_flight

    goal_list = []
    for goal in Goal.objects.filter(game=game):
        achieved = goal.achievers.filter(id=profile.id,
                achiever__timestamp__isnull=False).exists()
        goal_list.append([goal.city.name, achieved])

    stats = game.stats()

    json_str = json.dumps(
        {
            'time': date(now, 'P'),
            'airport': airport.name if airport else ticket.origin,
            'ticket': None if not ticket else ticket.to_dict(now),
            'messages': [{'id': i.id, 'text': i.text} for i in messages],
            'in_flight': in_flight,
            'goals': goal_list,
            'stats': stats,
            'player': user.username
        },
        default=DTHANDLER
    )
    return HttpResponse(json_str, mimetype='application/json')

@login_required
def flights(request):
    """render the flights widget for the user"""
    try:
        profile = request.user.profile
    except AttributeError:
        return HttpResponse('')

    try:
        game = profile.games.order_by('-timestamp')[0]
    except IndexError:
        return HttpResponse('')

    ticket = profile.ticket
    now, airport, ticket = game.update(profile)

    if ticket and ticket.in_flight(now):
        flights = ticket.destination.next_flights(game, now)
    elif airport:
        flights = airport.next_flights(game, now)
    else:
        flights = []

    # Annotate the flight objects with .remarks and .buyable
    for flight in flights:
        flight.remarks = flight.get_remarks(now)
        flight.buyable = flight.buyable(profile, now)

    return render_to_response(
            'airport/flights.html',
            {'flights': flights},
            RequestContext(request))

@login_required
def games_home(request):
    """Main games view"""
    try:
        open_game = Game.objects.exclude(state=0)
        open_game = open_game.filter(players=request.user.profile)[0]
        if request.user.profile in open_game.winners():
            open_game = None
    except IndexError:
        open_game = None
    airport_count = AirportMaster.objects.all().count()

    return render_to_response('airport/games.html', {
        'user': request.user.username,
        'open_game': open_game,
        'airport_count': airport_count
        },
        RequestContext(request)
    )

@login_required
def games_info(request):
    """Just another json view"""

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
        'airports__count')
    glist = []
    for game in games:
        glist.append(dict(
            id = game[0],
            players = game[1],
            host = escape(game[2]),
            goals = game[3],
            airports = game[4]))

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

    messages = Message.get_messages(request)

    data = {
            'games': glist,
            'current_game': current_game,
            'finished_current': finished_current,
            'messages': [{'id': i.id, 'text': i.text} for i in messages]
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

    return redirect(games_home)

@login_required
def games_join(request, game_id):
    """Join a game.  Game must exist and have not ended (you can join a
    game that is in progress
    """
    profile = request.user.profile

    game = get_object_or_404(Game, id=game_id)
    if game.state == 0:
        Message.send(profile, 'Could not join you to %s because it is over'
                % game)
    elif game.players.filter(id=profile.id).exists():
        Message.send(profile, 'You have already joined %s' % game)
    else:
        game.add_player(profile)

    return redirect(reverse(games_home))

@login_required
def games_stats(request):
    """Return user stats on game"""
    profile = request.user.profile
    games = profile.games

    context = dict()
    context['user'] = request.user
    context['game_count'] = games.count()
    context['won_count'] = profile.games_won.count()
    context['goal_count'] = profile.goals.count()
    context['goals_per_game'] = (
            1.0 * context['goal_count'] / context['game_count']
            if context['game_count']
            else 0)
    context['ticket_count'] = profile.tickets.count()
    context['tix_per_goal'] = (1.0 * context['ticket_count'] /
        context['goal_count'] if context['goal_count'] else 0)
    context['flight_hours'] = sum((i.flight.flight_time
        for i in profile.tickets)) / 60.0
    context['flight_hours_per_game'] = (context['flight_hours'] /
        context['game_count'] if context['game_count'] else 0)

    # average game time
    times = games.values('creation_time', 'timestamp')
    context['total_time'] = sum(((i['timestamp'] - i['creation_time'])
        .total_seconds() for i in times))
    context['avg_time'] = (
            1.0 * context['total_time'] / context['game_count']
            if context['game_count']
            else 0)
    # we really want hours though
    context['total_time'] = context['total_time'] / 3600.0 * Game.TIMEFACTOR
    context['avg_time'] = context['avg_time'] / 3600.0 * Game.TIMEFACTOR
    return render_to_response('airport/games_stats.html', context)

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
                messages.add_message(request, messages.INFO,
                    'Account activated. Please sign in.')
                return redirect(home)
        else:
            context['error'] = form._errors

    context['users'] = UserProfile.objects.all()
    return render_to_response('registration/register.html', context,
            RequestContext(request))

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

    return render_to_response(
            'airport/about.html',
            context,
            RequestContext(request)
    )

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

