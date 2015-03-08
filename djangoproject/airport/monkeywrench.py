"""
MonkeyWrenches are spontaneous events thrown in the game to produce some
unpredictableness.  They are things that happen to flights and airports
such as cancellations, delays, etc.

This module produces a MonkeyWrench base class, which does nothing,
subsequent MonkeyWrenches should subclass the class, and implement a
throw() method which actually does something.  It should also probably send
a broadcast message to the Game notifying players of what happened.

The MonkeyWrenchFactory collects all the various MonkeyWrench classes, and
when it's create() method is called, picks one at random, instantiates it
and returns it to the caller
"""
import datetime
import os
import random

from django.db.models import F, Count

from airport import logger, models


class MonkeyWrench(object):
    """A monkey wrench """

    def __init__(self, game, now=None):
        self.game = game
        self._now = now
        self.thrown = False

    def __str__(self):
        text = 'MonkeyWrench: {0}'
        return text.format(self.__class__.__name__)

    def throw(self):
        """throw this wrench"""
        self.thrown = True
        return

    @property
    def now(self):
        if not self._now:
            self._now = self.game.time
        return self._now


class CancelledFlight(MonkeyWrench):
    """Randomly Cancel a flight"""
    def throw(self):
        now = self.now
        flights = self.game.flights.filter(depart_time__gt=now)
        flight = models.choice(flights)
        if not flight:
            return
        flight.cancel(now)
        broadcast('Flight {num} from {origin} to {dest} is cancelled'.format(
            num=flight.number, origin=flight.origin.city.name,
            dest=flight.destination.city.name),
            self.game)
        self.thrown = True
        return


class DelayedFlight(MonkeyWrench):
    """Delay a flight that hasn't departed yet"""
    def throw(self):
        now = self.now
        flights = self.game.flights.filter(depart_time__gt=now)
        flight = models.choice(flights)
        if not flight:
            return
        minutes = random.randint(20, 60)
        timedelta = datetime.timedelta(minutes=minutes)
        try:
            flight.delay(timedelta, now)
        except flight.Finished:
            # damn, just missed it!
            return
        broadcast(('Flight {num} from {origin} to {dest} is delayed {min} '
                   'minutes'.format(num=flight.number,
                                    origin=flight.origin.city.name,
                                    dest=flight.destination, min=minutes)),
                  self.game)
        self.thrown = True
        return


class AllFlightsFromAirportDelayed(MonkeyWrench):
    """Take a random airport and delay all outgoing flights by a random
    number of minutes"""
    def throw(self):
        now = self.now
        airports = self.game.airports.all()
        airport = models.choice(airports)
        flights = self.game.flights.filter(origin=airport,
                                           depart_time__gt=now)
        minutes = random.randint(20, 60)
        timedelta = datetime.timedelta(minutes=minutes)
        for flight in flights:
            try:
                flight.delay(timedelta, now)
            except flight.Finished:
                continue
        broadcast(('Due to weather, all flights from {airport} are delayed'
                   ' {min} minutes'.format(airport=airport.code,
                                           min=minutes)),
                  self.game)
        self.thrown = True


class AllFlightsFromAirportCancelled(MonkeyWrench):
    """Cancel all future flights from a random airport"""
    def throw(self):
        now = self.now
        airports = self.game.airports.all()
        airport = models.choice(airports)
        flights = self.game.flights.filter(origin=airport,
                                           depart_time__gt=now)
        for flight in flights:
            flight.cancel(now)
        broadcast(('Due to weather, all flights from {airport} are'
                   ' cancelled'.format(airport=airport)),
                  self.game)
        self.thrown = True
        return


class DivertedFlight(MonkeyWrench):
    """Divert a flight to another airport"""
    reasons = (
        'Mayday! Flight {num} diverted to {dest}',
        'Unruly passenger on Flight {num}.  Emergency landing at {dest}.',
    )

    def throw(self):
        flights = models.Flight.objects.in_flight(self.game, self.now)
        flight = models.choice(flights)
        if not flight:
            return
        diverted_to = models.Airport.objects.filter(game=self.game)
        diverted_to = diverted_to.exclude(pk=flight.destination.pk)
        flight.destination = models.choice(diverted_to)
        flight.flight_time = models.City.get_flight_time(
            flight.origin,
            flight.destination,
            models.Flight.cruise_speed)
        flight.save()
        reason = random.choice(self.reasons)
        broadcast(
            reason.format(num=flight.number, dest=diverted_to), self.game)
        self.thrown = True


class MechanicalProblem(MonkeyWrench):
    """This is like diverted flight, but:

    * It diverts back to the originating airport and:
    * The flight time multiplied by how far it's travelled
    """
    def throw(self):
        flights = models.Flight.objects.in_flight(self.game, self.now)
        flights = flights.exclude(destination=F('origin'))
        flight = models.choice(flights)
        if not flight:
            return
        flight.destination = flight.origin
        time_travelled = self.game.time - flight.depart_time
        flight.flight_time = time_travelled.total_seconds() * 2 / 60
        flight.save()
        msg = 'Flight {0} is having mechanical problems and will return to {1}'
        msg = msg.format(flight.number, flight.origin)
        broadcast(msg, self.game)
        self.thrown = True


class LateFlight(MonkeyWrench):
    """Make an in-air flight run late"""
    MIN_LATENESS = 10  # Minutes
    MAX_LATENESS = 36
    RANDOM_MESSAGES = (
        'Flight {flight_number} is running {minutes} minutes late',
        'Flight {flight_number} caught some head wind. {minutes} minutes late',
        ('{destination}\'s controller fell asleep. '
         'Flight {flight_number} will arrive {minutes} minutes late')
    )

    def throw(self):
        flights = models.Flight.objects.in_flight(self.game, self.now)
        flight = models.choice(flights)
        if not flight:
            return
        minutes = random.randint(self.MIN_LATENESS, self.MAX_LATENESS)
        flight.flight_time = flight.flight_time + minutes
        flight.state = 'Delayed'
        flight.save()
        message = random.choice(self.RANDOM_MESSAGES)
        text = message.format(
            flight_number=flight.number,
            minutes=minutes,
            destination=flight.destination)
        broadcast(text, self.game)
        self.thrown = True
        return


class Hint(MonkeyWrench):
    """This isn't a monkey wrench at all, it actually is helpful.  It
    picks a random player of the game, finds their current goal, and sends a
    message telling them what (random) airport goes to that goal"""
    def throw(self):
        players = self.game.players.all()
        player = models.choice(players)
        if not player:
            return

        try:
            achievers = player.achievement_set.filter(
                game=self.game,
                timestamp=None)
            current_goal = achievers[0].goal.city
        except IndexError:
            return

        airports = self.game.airports.filter(destinations__city=current_goal)
        airport = models.choice(airports)

        if airport.city == current_goal:
            return

        msg = 'Hint: {0} goes to {1} ;-)'
        msg = msg.format(airport, current_goal.name)
        models.Message.objects.send(player, msg)
        self.thrown = True
        return


class TSA(MonkeyWrench):
    """Revoke a passenger's ticket just before the flight departs"""

    # we revoke the tickets just before departure (sneaky ;)
    minutes_before_departure = 15

    def throw(self):
        now = self.now
        max_depart_time = now + datetime.timedelta(
            minutes=self.minutes_before_departure)
        flights = self.game.flights.filter(depart_time__lte=max_depart_time)
        flights = self.game.flights.exclude(depart_time__lte=now)
        flights = flights.annotate(num_passengers=Count('passengers'))
        flights = list(flights.filter(num_passengers__gt=0))
        if not flights:
            return
        flight = random.choice(flights)
        passenger = random.choice(list(flight.passengers.all()))

        # kick him off!
        msg = ('Someone reported you as suspicious and you have been removed'
               ' from the plane.')
        models.Message.objects.send(passenger, msg,
                                    message_type='MONKEYWRENCH')
        passenger.ticket = None
        passenger.save()
        self.thrown = True


class FullFlight(MonkeyWrench):
    """Make a flight full so tickets can no longer be purchased"""
    def throw(self):
        now = self.now
        flights = self.game.flights.filter(
            depart_time__gt=now).filter(full=False)

        flight = models.choice(flights)
        if not flight:
            return

        flight.full = True
        flight.save()
        # no need to send a message
        self.thrown = True
        return


class TailWind(MonkeyWrench):
    """Apply tail wind to an in-flight flight, making it arrive earlier."""
    minimum_minutes = 15
    maximum_minutes = 28

    def throw(self):
        now = self.now
        min_arrival_time = now + datetime.timedelta(
            minutes=self.minimum_minutes)
        flights = models.Flight.objects.in_flight(self.game, now)
        flights = flights.filter(arrival_time__gt=min_arrival_time)
        flight = models.choice(flights)
        if not flight:
            return

        orig_arrival_time = int((flight.arrival_time - now).total_seconds())
        secs_to_shave = random.randint(
            self.minimum_minutes * 60,
            min(orig_arrival_time, self.maximum_minutes * 60))
        mins_to_shave = secs_to_shave // 60
        flight.arrival_time = flight.arrival_time - datetime.timedelta(
            minutes=mins_to_shave)
        flight.save()

        msg = 'Flight {0} caught some tail wind.  Arriving {1} minutes early.'
        msg = msg.format(flight.number, mins_to_shave)
        models.Message.objects.broadcast(msg, game=self.game,
                                         message_type='DEFAULT')
        self.thrown = True


class MonkeyWrenchFactory(object):
    """This factory is responsible for returning a new randomly chosen
    MonkeyWrench for a given game

    Usage:
    mwf = MonkeyWrenchFactory(game)
    mw = mwf.create()
    mw.throw()
    """
    def __init__(self):
        mw_test = os.environ.get('MONKEYWRENCH_TEST', None)
        if mw_test:
            self.wrenches = [globals()[mw_test]]
        else:
            self.wrenches = [
                i for i in globals().values()
                if type(i) is type and issubclass(i, MonkeyWrench)
            ]

    def create(self, game):
        """Create and return a new MonkeyWrench object"""
        wrench = random.choice(self.wrenches)(game)
        logger.debug('Throwing wrench: %s' % wrench)
        return wrench

    def test(self, wrench):
        """Only throw this *wrench*

        *wrench* is a MonkeyWrench (sub)class or a string representing one"""
        try:
            if issubclass(wrench, MonkeyWrench):
                self.wrenches = [wrench]
                return
        except TypeError:
            pass
        self.wrenches = [globals()[wrench]]


def broadcast(text, game):
    """Helper function, sends a Message.broadcast with
    message_type='MONKEYWRENCH'"""
    models.Message.objects.broadcast(
        text, game=game, message_type='MONKEYWRENCH')
