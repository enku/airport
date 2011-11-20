import datetime
import json
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.template.defaultfilters import date

from models import (Flight, FlightAlreadyDeparted, Message, UserProfile)

STARTTIME = datetime.datetime.now()
TIMEFACTOR = 60
MAX_SESSION_MESSAGES = getattr(settings, 'AIRPORT_MAX_SESSION_MESSAGES', 16)

# Remove all flights
Flight.objects.all().delete()

def get_time():
    now = datetime.datetime.now()

    difference = now - STARTTIME
    new_secs = difference.total_seconds() * TIMEFACTOR
    return STARTTIME + datetime.timedelta(seconds=new_secs)

@login_required
def home(request):
    """Main view"""

    time = get_time()
    user = request.user
    profile = user.get_profile()
    location = profile.location(time)
    airport = profile.airport
    ticket = profile.ticket
    next_flights = airport.next_flights(time)
    messages = request.session.get('messages', []) + Message.get_messages(user)
    context = RequestContext(request)

    if ticket:
        in_flight = ticket.in_flight(time)
    else:
        in_flight = False

    if not request.session.get('in_flight', False) and in_flight:
        # newly, in flight. Make an announcement
        Message.announce(user, '%s has left %s' % (user, ticket.origin))
    request.session['in_flight'] = in_flight

    if not in_flight and next_flights.count() == 0:
        airport.create_flights(time)
        next_flights = airport.next_flights(time)

    if request.method == 'POST':
        # Buying a ticket
        buy  = [i for i in request.POST if i.startswith('buy_')][0]
        flight_no = int(buy[4:])
        flight = get_object_or_404(Flight, number=flight_no)

       # try to buy the ticket
        try:
           profile.buy_ticket(flight, time)
        except FlightAlreadyDeparted:
            Message.send(profile, 'Flight %s has already left' % flight.number)
        request.session['messages'] = messages[-MAX_SESSION_MESSAGES:]
        return redirect(home)

    request.session['messages'] = messages[-MAX_SESSION_MESSAGES:]
    return render_to_response('airport/home.html',
            {
                'user': user,
                'profile': profile,
                'airport': airport,
                'ticket': ticket,
                'time': time,
                'next_flights': next_flights,
                'messages': messages,
                'in_flight': in_flight
            },
            context_instance=context
    )

@login_required
def info(request):
    """Used ajax called to be used by the home() view.
    Returns basically all the info needed by home() but as as json
    dictionary"""
    time = get_time()
    user = request.user
    profile = user.get_profile()
    location = profile.location(time)
    airport = profile.airport
    ticket = profile.ticket
    next_flights = airport.next_flights(time)
    messages = request.session.get('messages', []) + Message.get_messages(user)
    dthandler = lambda obj: obj.isoformat() if isinstance(obj, datetime.datetime) else None

    if ticket:
        in_flight = ticket.in_flight(time)
    else:
        in_flight = False

    if not request.session.get('in_flight', False) and in_flight:
        Message.announce(user, '%s has left %s' % (user,
            ticket.origin))
    request.session['in_flight'] = in_flight
    if not in_flight and next_flights.count() == 0:
        airport.create_flights(time)
        next_flights = airport.next_flights(time)


    nf_list = []
    for next_flight in next_flights:
        nf_dict = next_flight.to_dict()
        nf_dict['buyable'] = (nf_dict['status'] != 'CANCELLED'
                and next_flight.depart_time > time
                and next_flight != ticket
        )


        nf_list.append(nf_dict)

    json_str = json.dumps(
        {
            'time': date(time, 'P'),
            'location': str(location),
            'airport': airport.name,
            'ticket': None if not ticket else ticket.to_dict(),
            'next_flights': nf_list,
            'messages': [i.text for i in messages],
            'in_flight': in_flight
        },
        default=dthandler
    )
    request.session['messages'] = messages[-MAX_SESSION_MESSAGES:]
    return HttpResponse(json_str, mimetype='application/json')

