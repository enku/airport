"""
Django views for the airport app
"""
import datetime
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.template.defaultfilters import date
from django.views.generic import TemplateView

from airport.models import (Flight,
        FlightAlreadyDeparted,
        Game,
        Goal,
        Message,
        Purchase)

DTHANDLER = lambda obj: (obj.isoformat()
        if isinstance(obj, datetime.datetime) else None)
NUM_GOALS = 3

@login_required
def home(request):
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
        most_recent_game = Game.objects.all().order_by('-timestamp')[0]
        if most_recent_game.state == 1:
            # game in progress, continue
            game = most_recent_game
        elif most_recent_game.state == -1:
            # not yet started
            game = most_recent_game
            game.begin()
        else:
            # game over, create new game
            game = Game.create(profile, NUM_GOALS)
            game.begin()
    except IndexError:
        game = Game.create(profile, NUM_GOALS)
        game.begin()

    if profile not in game.players.all():
        game.add_player(profile)

    now, airport, ticket = game.update(profile)
    print 'Game: %s\nTime: %s' % (game.id, date(now, 'P'))

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
        nf_dict['buyable'] = (nf_dict['status'] != 'CANCELLED'
                and next_flight.depart_time > now
                and next_flight != ticket
        )


        nf_list.append(nf_dict)

    goal_list = []
    for goal in Goal.objects.filter(game=game):
        achieved = goal.achievers.filter(id=profile.id,
                achiever__timestamp__isnull=False).exists()
        goal_list.append([goal.city.name, achieved])

    json_str = json.dumps(
        {
            'time': date(now, 'P'),
            'airport': airport.name if airport else ticket.origin,
            'ticket': None if not ticket else ticket.to_dict(now),
            'next_flights': nf_list,
            'messages': [i.text for i in messages],
            'in_flight': in_flight,
            'goals': goal_list,
            'player': user.username
        },
        default=DTHANDLER
    )
    return HttpResponse(json_str, mimetype='application/json')

def crash(_request):
    """Case the app to crash"""
    raise Exception('Crash forced!')
