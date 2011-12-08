# -*- encoding: utf-8 -*-
"""
MonkeyWrenches are spontaneous events thrown in the game to produce some
unpredictableness.  They are things that happen to flights and airports
such as cancellations, delays, etc.

This module produces a MonkeyWrench base class, which does nothing,
subsecrent MonkeyWrenches should subclass the class, and implement a
throw() method which actually does something.  It should also probably send
a broadcast message to the Game notifying players of what happened.

The MonkeyWrenchFactory collects all the various MonkeyWrench classes, and
when it's create() method is called, picks one at random, instantiates it
and returns it to the caller
"""

import datetime
import random

from airport.models import (
    Airport,
    Flight,
    FlightFinished,
    Goal,
    Message,
    UserProfile
)

class MonkeyWrench(object):
    """A monkey wrench ☺"""

    def __init__(self, game):
        self.game = game
        self.thrown = False

    def throw(self):
        """throw this wrench"""
        self.thrown = True
        return

    def flights_in_the_air(self):
        """Return a list of flights currently in the air"""
        now = self.game.time
        in_flight = []
        flights = Flight.objects.filter(game=self.game, depart_time__lt=now)
        for flight in flights:
            if flight.in_flight(now):
                in_flight.append(flight)

        return in_flight

class CancelledFlight(MonkeyWrench):
    """Randomly Cancel a flight"""
    def throw(self):
        now = self.game.time
        flight = Flight.objects.filter(game=self.game,
                depart_time__gt=now).order_by('?')
        if not flight.exists():
            return
        flight = flight[0]
        flight.cancel(now)
        Message.broadcast('Flight %s from %s to %s is cancelled' %
                (flight.number, flight.origin.city.name,
                    flight.destination.city.name), self.game)
        self.thrown = True
        return

class DelayedFlight(MonkeyWrench):
    """Delay a flight that hasn't departed yet"""
    def throw(self):
        now = self.game.time
        flight = Flight.objects.filter(game=self.game,
                depart_time__gt=now).order_by('?')
        if not flight.exists():
            return
        flight = flight[0]
        minutes = random.randint(20, 60)
        timedelta = datetime.timedelta(minutes=minutes)
        try:
            flight.delay(timedelta, now)
        except FlightFinished:
            # damn, just missed it!
            return
        Message.broadcast(
            'Flight %s from %s to %s is delayed %s minutes' %
            (flight.number, flight.origin.city.name,
                flight.destination, minutes),
            self.game)
        self.thrown = True
        return

class AllFlightsFromAirportDelayed(MonkeyWrench):
    def throw(self):
        now = self.game.time
        airport = Airport.objects.all().order_by('?')[0]
        flights = Flight.objects.filter(game=self.game, origin=airport,
                depart_time__gt=now)
        minutes = random.randint(20, 60)
        timedelta = datetime.timedelta(minutes=minutes)
        for flight in flights:
            try:
                flight.delay(timedelta, now)
            except FlightFinished:
                continue
        Message.broadcast(
            'Due to weather, all flights from %s are delayed %s minutes' %
            (airport.code, minutes), self.game)

class AllFlightsFromAirportCancelled(MonkeyWrench):
    def throw(self):
        now = self.game.time
        airport = Airport.objects.all().order_by('?')[0]
        flights = Flight.objects.filter(game=self.game, origin=airport,
                depart_time__gt=now)
        for flight in flights:
            flight.cancel(now)
        Message.broadcast(
            'Due to weather, all flights from %s are cancelled' %
            airport.city.name, self.game)
        self.thrown = True
        return

class DivertedFlight(MonkeyWrench):
    """Divert a flight to another airport"""
    def throw(self):
        flights = self.flights_in_the_air()
        if not flights:
            return
        flight = random.choice(flights)
        diverted_to = (Airport.objects
                .exclude(id=flight.destination.id)
                .order_by('?')[0])
        flight.destination = diverted_to
        flight.save()
        Message.broadcast(
            'Mayday! Flight %d diverted to %s' % (flight.number,
                diverted_to),
            self.game)
        self.thrown = True
        return

class Hint(MonkeyWrench):
    """This isn't a monkey wrench at all, it actually is helpful.  It
    picks a random user of the game, finds their current goal, and sends a
    message telling them what (random) airport goes to that goal"""
    def throw(self):
        try:
            profile = (UserProfile.objects
                        .filter(game=self.game)
                        .order_by('?')[0])
        except IndexError:
            return

        try:
            achievers = profile.achiever_set.filter(
                    game=self.game,
                    timestamp=None)
            current_goal = achievers[0].goal.city
        except IndexError:
            return

        airport_to_goal = (Airport.objects.filter(
                destinations__city=current_goal)
                .order_by('?')[0])

        if airport_to_goal.city == current_goal:
            return

        Message.send(profile, u'Hint: %s goes to %s ;-)' % (
                airport_to_goal, current_goal))
        return

class MonkeyWrenchFactory(object):
    """This factory is responsible for returning a new randomly chosen
    MonkeyWrench for a given game

    Usage:
    >>> mwf = MonkeyWrenchFactory(game)
    >>> mw = mwf.create()
    """
    def __init__(self):
        self.wrenches = [i for i in globals().values()
                if type(i) is type and issubclass(i, MonkeyWrench)]

    def create(self, game):
        """Create and return a new MonkeyWrench object"""
        return random.choice(self.wrenches)(game)

