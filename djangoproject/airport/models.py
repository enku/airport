# -*- encoding: utf-8 -*-
"""Models for the airport django app"""

import datetime
import random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.template.defaultfilters import date

MIN_FLIGHT_TIME = getattr(settings, 'MIN_FLIGHT_TIME', 30)
MAX_FLIGHT_TIME = getattr(settings, 'MAX_FLIGHT_TIME', 120)

class FlightBaseException(Exception):
    """Base Exception for scheduling/ticketing errors"""
    def __init__(self, flight, *args):
        self.flight = flight
        super(FlightBaseException, self).__init__(*args)

class FlightAlreadyDeparted(FlightBaseException):
    """A Flight is already departed"""
    pass

class FlightNotAtDepartingAirport(FlightBaseException):
    """Exception raised when a player attempts to purchase a flight at a
    different airport than they are located in"""
    pass

class FlightFinished(FlightBaseException):
    """Flight has already landed or is cancelled"""
    pass


class City(models.Model):
    """A City"""
    name = models.CharField(max_length=50, unique=True)

    def __unicode__(self):
        return self.name


    class Meta:
        """metadata"""
        verbose_name_plural = 'cities'


class Airport(models.Model):
    """An Airport"""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=4)
    city = models.ForeignKey(City)
    destinations = models.ManyToManyField('self', null=True, blank=True)

    def __unicode__(self):
        aiports_per_city = Airport.objects.filter(city=self.city).count()
        if aiports_per_city > 1:
            return u'%s (%s)' % (self.city.name, self.code)
        return self.city.name

    __str__ = __unicode__

    def next_flights(self, now):
        """Return outgoing flights for airport, but not past flights"""

        return self.flights.filter(depart_time__gt=now)

    def clean(self):
        """validation"""
        # airport destinations can't be in the same city
        if self.destinations.filter(city=self.city).exists():
            raise ValidationError(
                u'Airport cannot have itself as a destination.')

    def next_flight_to(self, city, now):
        """Return the next flight to «city» or None"""
        if isinstance(city, Airport):
            city = city.city
        next_flights = self.next_flights(now).filter(
                destination__city=city)

        if next_flights.exists():
            return next_flights[0]
        return None

    def create_flights(self, now):
        """Create some flights starting from «now»"""
        cushion = 20 # minutes

        for destination in self.destinations.all():
            Flight.objects.create(
                    origin = self,
                    destination = destination,
                    depart_time = (datetime.timedelta(minutes=cushion) +
                        random_time(now)),
                    flight_time = random.randint(MIN_FLIGHT_TIME,
                        MAX_FLIGHT_TIME))


class Flight(models.Model):
    """A flight from one airport to another"""

    # NOTE: this is really a staticmethod, but if i decorate it with
    # staticmethod() then Django chokes on the number field declaration
    # because it doens't think the decorated method is "callable".  This is
    # either a Python problem or a Django problem, but I've encoutered it
    # before and it is quite annoying
    def random_flight_number():
        """Return a random number, not already a flight number"""
        while True:
            number = random.randint(1, 6666)
            flight = Flight.objects.filter(number=number)
            if flight.exists():
                continue
            return number

    number = models.IntegerField(default=random_flight_number)
    origin = models.ForeignKey(Airport, related_name='flights')
    destination = models.ForeignKey(Airport, related_name='+')
    depart_time = models.DateTimeField()
    flight_time = models.IntegerField()
    delayed = models.BooleanField(default=False)

    def __unicode__(self):
        return u'%s from %s to %s departing %s' % (self.number,
                self.origin.name, self.destination.name, self.depart_time)

    @property
    def arrival_time(self):
        """Compute and return the arrival time for this flight"""
        return self.depart_time + datetime.timedelta(minutes=self.flight_time)

    @property
    def destination_city(self):
        """Return the City of the destination for this Flight"""
        return self.destination.city

    @property
    def origin_city(self):
        """Return the City of the origin for this Flight"""
        return self.origin.city

    def in_flight(self, now):
        """Return true if flight is in the air"""
        if self.flight_time == 0:
            return False


        if self.depart_time <= now <= self.arrival_time:
            return True

        return False

    def has_landed(self, now):
        """Return True iff flight has landed"""

        if self.flight_time == 0:
            return False

        return (now >= self.arrival_time)

    @property
    def cancelled(self):
        """Return True iff a flight is cancelled"""
        return self.flight_time == 0

    def cancel(self, now):
        """Cancel a flight. In-flight flights (obviously) can't be
        cancelled"""

        if not self.in_flight(now):
            self.flight_time = 0
            self.save()

        else:
            raise FlightAlreadyDeparted(self,
                    'In-progress flight cannot be cancelled')

    def delay(self, timedelta, now):
        """Delay the flight by «timedelta»"""
        now = now or datetime.datetime.now()

        if self.in_flight(now) or self.has_landed(now):
            raise FlightAlreadyDeparted(self)

        if self.flight_time == 0:
            raise FlightFinished(self)

        self.depart_time = self.depart_time + timedelta
        self.delayed = True
        self.save()

    def to_dict(self):
        """Helper method to return Flight as a json-serializable dict"""
        if self.cancelled:
            status = 'Cancelled'
        elif self.delayed:
            status = 'Delayed'
        else:
            status = 'On time'

        return {
            'number': self.number,
            'depart_time': date(self.depart_time, 'P'),
            'arrival_time': date(self.arrival_time, 'P'),
            'destination': str(self.destination),
            'status': status,
        }


    def clean(self, *_args, **_kwargs):
        """Validate the model"""

        # Origin can't also be desitination
        if self.origin == self.destination:
            raise ValidationError(u'Origin and destination cannot be the same')

        if self.origin.desitinations.filter(id=self.destination.id).exists():
            raise ValidationError(u'%s not accessible from %s' %
                    (self.destination.code, self.origin.code))


    class Meta:
        """metadata"""
        ordering = ['depart_time']


def random_time(now, maximum=60):
    """Helper function, return a random time in the future (from «now»)
    with a maximium of «maximum» minutes in the future"""
    # this is ghetto
    times = [now + datetime.timedelta(minutes=i) for i in range(maximum)]
    return random.choice(times)


class UserProfile(models.Model):
    """Profile for players"""
    user = models.ForeignKey(User)
    airport = models.ForeignKey(Airport, null=True, blank=True)
    ticket = models.ForeignKey(Flight, null=True, blank=True)

    def __unicode__(self):
        return u'Profile for %s' % self.user.username

    def location(self, now):
        """Update and return user's current location info

        This updates «ticket» and «airport» properties and returns either a
        «Flight» object or an «Airport» object depending on whether the User
        is currently in flight or not

        All views should call this method on the user when the view is
        first called, and subsequently after flights are purchased if
        updated location data is needed.  Ideally this would be
        automagically called but we haven't researched on how to do that
        yet, so views call this manually!"""
        if self.ticket:
            if self.ticket.in_flight(now):
                return self.ticket
            elif self.ticket.has_landed(now):
                self.airport = self.ticket.destination
                self.ticket = None
                self.save()
                for profile in UserProfile.objects.exclude(id=self.id):
                    Message.objects.create(profile=profile,
                        text='%s has arrived at %s' % (self.user.username,
                            self.airport)
                    )
                return self.airport

        return self.airport

    def purchase_flight(self, flight, now):
        """Purchase a flight.  User must be at the origin airport and must be a
        future flight"""

        if isinstance(self.location(now), Flight):
            raise FlightAlreadyDeparted(flight,
                    'Cannot purchase a flight while in flight')

        if self.location(now) != flight.origin:
            raise FlightNotAtDepartingAirport(flight,
                'Must be at the departing airport (%s) to purchase flight' %
                flight.origin)

        if flight.depart_time <= now:
            raise FlightAlreadyDeparted(flight, 'Flight already departed')

        self.ticket = flight
        self.save()



User.profile = property(lambda u: UserProfile.objects.get_or_create(user=u)[0])

class Message(models.Model):
    """Messages for users"""
    text = models.CharField(max_length=255)
    profile = models.ForeignKey(UserProfile, related_name='messages')

    def __unicode__(self):
        return self.text

    @classmethod
    def broadcast(cls, text):
        """Send a message to all users with a UserProfile"""
        for profile in UserProfile.objects.all():
            cls.objects.create(profile=profile, text=text)

    @classmethod
    def announce(cls, announcer, text):
        """Sends a message to all users but «announcer»"""
        if isinstance(announcer, User):
            # we want the UserProfile, but allow the caller to pass User as well
            announcer = announcer.get_profile()

        for profile in UserProfile.objects.exclude(id=announcer.id):
            cls.objects.create(profile=profile, text=text)

    @classmethod
    def send(cls, user, text):
        """Send a unicast message to «user» return the Message object"""
        if isinstance(user, User):
            # we want the UserProfile, but allow the caller to pass User as well
            user = user.get_profile()

        return cls.objects.create(profile=user, text=text)

    @classmethod
    def get_messages(cls, user, purge=True):
        """Get messages for «user» (as a list)
            if «purge»=True (default), delete the messages"""
        # This should really be in a model manager, but i'm too lazy

        if isinstance(user, User):
            # we want the UserProfile, but allow the caller to pass User as well
            user = user.get_profile()

        messages_qs = cls.objects.filter(profile=user)
        messages_list = list(messages_qs)
        if purge:
            messages_qs.delete()
        return messages_list
