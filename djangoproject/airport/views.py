"""
Django views for the airport app
"""
import datetime
import json
import random

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template.defaultfilters import date

from airport.models import (Flight,
        FlightAlreadyDeparted,
        Game,
        Goal,
        Message,
        Purchase)
from airport.monkeywrench import MonkeyWrenchFactory

DTHANDLER = lambda obj: (obj.isoformat()
        if isinstance(obj, datetime.datetime) else None)
MW_PROBABILITY = getattr(settings, 'MONKEYWRENCH_PROBABILITY', 20)
MWF = MonkeyWrenchFactory()

@login_required
def home(_request):
    """Main view"""
    return render_to_response('airport/home.html')


@login_required
def info(request):
    """Used ajax called to be used by the home() view.
    Returns basically all the info needed by home() but as as json
    dictionary"""
    user = request.user
    profile = user.profile

    try:
        game = Game.objects.all().order_by('-timestamp')[0]
        if game.state == 1 and game.players.filter(id=profile.id).exists():
            # game in progress, continue unless you've already won
            if profile in game.winners():
                return json_redirect(reverse(games_home))

        elif game.state == -1 and game.host == profile:
            game.begin()
            Message.broadcast('%s has started %s' % (game.host.user.username,
                game), game)
        elif game.state == -1 and game.players.filter(id=profile.id).exists():
            message = ('Waiting for %s to start %s' %
                (game.host.user.username, game))
            messages = Message.get_messages(request, purge=False)
            if message not in [i.text for i in messages]:
                Message.send(profile, message)

        elif game.state == 0:
            # game over
            Message.send(profile, '%s ended' % game)
            return json_redirect(reverse(games_home))
        else:
            return json_redirect(reverse(games_home))
    except IndexError:
        return json_redirect(reverse(games_home))

    if random.randint(1, MW_PROBABILITY) == MW_PROBABILITY:
        MWF.create(game).throw()

    now, airport, ticket = game.update(profile)

    if request.method == 'POST':
        if 'selected' in request.POST:
            flight_no = int(request.POST['selected'])
            flight = get_object_or_404(Flight, game=game, number=flight_no)

            # try to purchase the flight
            try:
                profile.purchase_flight(flight, now)
                ticket = flight
            except FlightAlreadyDeparted:
                Message.send(profile, 'Flight %s has already left' % flight.number)
            return redirect(info)

    if ticket and ticket.in_flight(now):
        next_flights = ticket.destination.next_flights(game, now)
    elif airport:
        next_flights = airport.next_flights(game, now)
    else:
        next_flights = []

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

    nf_list = []
    for next_flight in next_flights:
        nf_dict = next_flight.to_dict(now)
        nf_dict['buyable'] = (nf_dict['status'] != 'Cancelled'
                and next_flight.depart_time > now
                and next_flight != ticket
        )


        nf_list.append(nf_dict)

    goal_list = []
    for goal in Goal.objects.filter(game=game):
        achieved = goal.achievers.filter(id=profile.id,
                achiever__timestamp__isnull=False).exists()
        goal_list.append([goal.city.name, achieved])

    stats = []
    for player in game.players.all().distinct():
        stats.append([player.user.username, game.goals_achieved_for(player)])

    json_str = json.dumps(
        {
            'time': date(now, 'P'),
            'airport': airport.name if airport else ticket.origin,
            'ticket': None if not ticket else ticket.to_dict(now),
            'next_flights': nf_list,
            'messages': [i.text for i in messages],
            'in_flight': in_flight,
            'goals': goal_list,
            'stats': stats,
            'player': user.username
        },
        default=DTHANDLER
    )
    return HttpResponse(json_str, mimetype='application/json')

@login_required
def games_home(request):
    """Main games view"""
    return render_to_response('airport/games.html', {
        'user': request.user.username
        }
    )

@login_required
def games_info(request):
    """Just another json view"""

    # active games
    games = Game.objects.annotate(Count('players', distinct=True))
    games = games.annotate(Count('goals', distinct=True))
    games = games.exclude(state=0)
    games = games.values('id', 'players__count', 'goals__count')
    games = list(games)

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
            'games': games,
            'current_game': current_game,
            'finished_current': finished_current,
            'messages': [i. text for i in messages]
    }
    return HttpResponse(json.dumps(data), mimetype='application/json')

@login_required
def games_create(request, goals):
    """Create a game, or if the user is currently in a non-closed game,
    send a message saying they can't create a game(yet).  Finally, redirect
    to the games view
    """
    user = request.user
    profile = user.profile
    goals = int(goals)

    games = Game.objects.exclude(state=0, players=profile)
    if games.exists():
        Message.send(profile, ('Cannot create a game since you are '
            'already playing an open game.'))
    else:
        game = Game.create(profile, goals)
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


def crash(_request):
    """Case the app to crash"""
    raise Exception('Crash forced!')

def json_redirect(url):
    """Return a simple json dictionary with a redirect key and url value"""
    return HttpResponse(
        json.dumps({'redirect': url}),
        mimetype='application/json'
    )

