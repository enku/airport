# -*- encoding: utf-8 -*-
"""Models for the airport django app"""

import datetime
import random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db import transaction
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
    destinations = models.ManyToManyField('self', null=True, blank=True,
            symmetrical=True)

    def __unicode__(self):
        aiports_per_city = Airport.objects.filter(city=self.city).count()
        if aiports_per_city > 1:
            return u'%s (%s)' % (self.city.name, self.code)
        return self.city.name

    __str__ = __unicode__

    def next_flights(self, game, now, future_only=False, auto_create=True):
        """Return next Flights out from «self», creating new flights if
        necessary.  Return the list of flights ordered by destination city
        name

        If «future_only» is True, only return future flights.  By default,
        will also return Flights that have already departed.  This is so
        the views that need flights can also display historical flights.
        If you only want future flights, pass "future_only=True"

        If «auto_create» is True (default), automagically create fututure
        flights
        """

        # TODO: this is an ugly method.  Refactor!

        future_flights = self.flights.filter(game=game, depart_time__gt=now)

        if not future_only:
            other_flights = Flight.objects.filter(game=game, origin=self)[:10]
        else:
            other_flights = Flight.objects.none()

        if future_flights.count() == 0 and auto_create:
            future_flights = self.create_flights(game, now)

        flight_set = set(future_flights).union(set(other_flights[:10 -
            min(future_flights.count(), 10)]))
        flight_list = list(flight_set)
        flight_list.sort(key=lambda flight: flight.destination.city.name)
        return flight_list

    def clean(self):
        """validation"""
        # airport destinations can't be in the same city
        if self.destinations.filter(city=self.city).exists():
            raise ValidationError(
                u'Airport cannot have itself as a destination.')

    def next_flight_to(self, game, city, now):
        """Return the next flight to «city» or None"""
        if isinstance(city, Airport):
            city = city.city
        next_flights = self.next_flights(game, now, future_only=True,
                auto_create=False)
        next_flights = [i for i in next_flights if i.depart_time >= now and
                i.destination.city == city]
        next_flights.sort(key=lambda flight: flight.depart_time)

        if next_flights:
            return next_flights[0]
        return None

    def create_flights(self, game, now):
        """Create some flights starting from «now»"""
        cushion = 20 # minutes

        flight_ids = []
        for destination in self.destinations.all().distinct():
            flight = Flight.objects.create(
                    game = game,
                    origin = self,
                    destination = destination,
                    depart_time = (datetime.timedelta(minutes=cushion) +
                        random_time(now)),
                    flight_time = random.randint(MIN_FLIGHT_TIME,
                        MAX_FLIGHT_TIME))
            flight_ids.append(flight.id)
        transaction.commit()
        return Flight.objects.filter(id__in=flight_ids)


class Flight(models.Model):
    """A flight from one airport to another"""

    # NOTE: this is really a staticmethod, but if i decorate it with
    # staticmethod() then Django chokes on the number field declaration
    # because it doens't think the decorated method is "callable".  This is
    # either a Python problem or a Django problem, but I've encoutered it
    # before and it is quite annoying

    game = models.ForeignKey('Game', null=False)
    number = models.IntegerField(editable=False)
    origin = models.ForeignKey(Airport, related_name='flights')
    destination = models.ForeignKey(Airport, related_name='+')
    depart_time = models.DateTimeField()
    flight_time = models.IntegerField()
    delayed = models.BooleanField(default=False)

    def __unicode__(self):
        return u'%s from %s to %s departing %s' % (
                self.number,
                self.origin.code,
                self.destination.code,
                date(self.depart_time, 'P'))

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

    def to_dict(self, now):
        """Helper method to return Flight as a json-serializable dict"""
        if self.cancelled:
            status = 'Cancelled'
        elif self.delayed:
            status = 'Delayed'
        elif self.depart_time < now:
            if self.in_flight(now):
                status = 'Departed'
            else:
                status = 'Arrived'
        else:
            status = 'On time'

        return {
            'number': self.number,
            'depart_time': date(self.depart_time, 'P'),
            'arrival_time': date(self.arrival_time, 'P'),
            'origin': str(self.origin),
            'destination': str(self.destination),
            'status': status,
        }

    @property
    def passengers(self):
        """Return a qs of passengers (UserProfile) on this «Flight»"""
        return UserProfile.objects.filter(ticket=self)

    def save(self, *args, **kwargs):
        """Overriden .save() method for Flights"""
        # we need a unique fligth # for this game
        if not self.number:
            self.number = self.random_flight_number()

        return super(Flight, self).save(*args, **kwargs)

    def random_flight_number(self):
        """Return a random number, not already a flight number"""
        while True:
            number = random.randint(100, 9999)
            flight = Flight.objects.filter(game=self.game, number=number)
            if flight.exists():
                continue
            return number

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


def random_time(now, maximum=40):
    """Helper function, return a random time in the future (from «now»)
    with a maximium of «maximum» minutes in the future"""

    flight_time = random.randint(0, maximum)
    return now + datetime.timedelta(minutes=flight_time)

class UserProfile(models.Model):
    """Profile for players"""
    user = models.ForeignKey(User)
    airport = models.ForeignKey(Airport, null=True, blank=True)
    ticket = models.ForeignKey(Flight, null=True, blank=True)

    def __unicode__(self):
        return u'Profile for %s' % self.user.username

    def location(self, now, game):
        """Update and return user's current location info

        info is a tuple of (Airport or None, Flight or None)

        This updates «ticket» and «airport» properties and returns either a
        «Flight» object or an «Airport» object depending on whether the User
        is currently in flight or not
        """
        if self.ticket:
            if self.ticket.in_flight(now):
                return (None, self.ticket)
            elif self.ticket.has_landed(now):
                if self.airport != self.ticket.destination:
                    self.airport = self.ticket.destination
                    self.ticket = None
                    self.save()
                    Message.announce(self, '%s has arrived at %s' %
                            (self.user.username, self.airport), game)

                    return (self.airport, None)

        self.save()
        return (self.airport, self.ticket)

    def purchase_flight(self, flight, now):
        """Purchase a flight.  User must be at the origin airport and must be a
        future flight"""

        if self.ticket and self.ticket.in_flight(now):
            raise FlightAlreadyDeparted(flight,
                    'Cannot purchase a flight while in flight')

        if self.airport != flight.origin:
            raise FlightNotAtDepartingAirport(flight,
                'Must be at the departing airport (%s) to purchase flight' %
                flight.origin)

        if flight.depart_time <= now:
            raise FlightAlreadyDeparted(flight, 'Flight already departed')

        self.ticket = flight
        self.save()

    def save(self, *args, **kwargs):
        new_user = not self.id
        super(UserProfile, self).save(*args, **kwargs)
        if new_user:
            Message.send(self, 'Welcome to Airport!')

User.profile = property(lambda u: UserProfile.objects.get_or_create(user=u)[0])

class Message(models.Model):
    """Messages for users"""
    text = models.CharField(max_length=255)
    profile = models.ForeignKey(UserProfile, related_name='messages')

    def __unicode__(self):
        return self.text

    @classmethod
    def broadcast(cls, text, game=None):
        """Send a message to all users in «game» with a UserProfile"""
        print 'BROADCAST: %s' % text

        if game:
            profiles = UserProfile.objects.filter(game=game).distinct()
        else:
            profiles = UserProfile.objects.all()

        for profile in profiles:
            cls.objects.create(profile=profile, text=text)

    @classmethod
    def announce(cls, announcer, text, game=None):
        """Sends a message to all users but «announcer»"""
        print 'ANNOUNCE: %s' % text

        if isinstance(announcer, User):
            # we want the UserProfile, but allow the caller to pass User as well
            announcer = announcer.profile

        if game:
            profiles = UserProfile.objects.filter(game=game).distinct()
        else:
            profiles = UserProfile.objects.all()

        for profile in profiles.exclude(id=announcer.id).distinct():
            cls.objects.create(profile=profile, text=text)

    @classmethod
    def send(cls, user, text):
        """Send a unicast message to «user» return the Message object"""
        if isinstance(user, User):
            # we want the UserProfile, but allow the caller to pass User as well
            user = user.get_profile()

        print 'MESSAGE(%s): %s' % (user.user.username, text)

        cls.objects.create(profile=user, text=text)

    @classmethod
    def get_messages(cls, user, purge=True):
        """Get messages for «user» (as a list)
            if «purge»=True (default), delete the messages"""
        # This should really be in a model manager, but i'm too lazy

        if isinstance(user, User):
            # we want the UserProfile, but allow the caller to pass User as well
            user = user.profile

        messages_qs = cls.objects.filter(profile=user)
        messages_list = list(messages_qs)
        if purge:
            messages_qs.delete()
        return messages_list

class Game(models.Model):
    """This is a game.  A Game is hosted and has it's own game time and
    players and stuff like that.  A Game is either not started, in progress or
    ended.

    A game has goals, which is a list of airport (in order) that each player
    must go to.  The Game keeps track of which players have achieved which
    goals.

    The Game is the God of Airport"""
    STATE_CHOICES = (
            (-1, 'Not Started'),
            ( 0, 'Game Over'),
            ( 1, 'In Progress'))

    TIMEFACTOR = 60

    host = models.ForeignKey(UserProfile, related_name='+')
    #        null=True, blank=True, on_delete=models.SET_NULL)
    players = models.ManyToManyField(UserProfile, null=True, blank=True,
            through='Achiever')
    state = models.SmallIntegerField(choices=STATE_CHOICES, default=-1)
    start_airport = models.ForeignKey(Airport, related_name='+')
    goals = models.ManyToManyField(City, through='Goal')
    timestamp = models.DateTimeField(auto_now_add=True)


    def __unicode__(self):
        return u'Game %s' % self.pk

    @classmethod
    def create(cls, host, num_goals=1):
        """Create a new «Game»"""
        cities = City.objects.all()
        game = cls.objects.create(
                host=host,
                state = -1,
                start_airport = Airport.objects.all().order_by('?')[0]
        )
        game.add_player(host)
        # add goals
        goal_cities = random.sample(cities.exclude(
            id=game.start_airport.city.id), num_goals)
        for i, goal_city in enumerate(goal_cities):
            Goal.objects.create(
                    city = goal_city,
                    game = game,
                    order = i + 1
            )
        Message.broadcast('Game %s created' % game)
        return game

    def begin(self):
        """start the game"""
        for player in self.players.all():
            player.airport = self.start
            player.game = self
            player.save()

        self.state = 1
        self.timestamp = datetime.datetime.now()
        self.save()

    def end(self):
        """End the Game"""
        self.state = 0
        self.timestamp = datetime.datetime.now()
        self.save()
        for player in self.players.all():
            player.game = None
            player.save()
        Message.broadcast('%s has ended!' % self, self)

    def add_player(self, profile):
        """Add player to profile if game hasn't ended"""
        if self.state == 0:
            return

        if profile in self.players.all():
            return

        # This is a pain in the ass to do, basically we need to create an
        # Achiever model for each goal
        for goal in Goal.objects.filter(game=self):
            Achiever.objects.create(
                    profile=profile,
                    goal = goal,
                    game = self)

        # put the player at the starting airport and take away their
        # tickets
        profile.ticket = None
        profile.airport = self.start_airport
        profile.save()

        # Delete player messages
        Message.objects.filter(profile=profile).delete()

        # Send out an announcement
        Message.broadcast('%s has entered game %s' % (profile.user.username,
                    self.id), self)
        # put the player at the starting airport and take away their
        # tickets
        profile.ticket = None
        profile.airport = self.start_airport
        profile.save()

    @property
    def time(self):
        """Return current game time"""
        now = datetime.datetime.now()

        if self.state != 1:
            return now

        difference = now - self.timestamp
        new_secs = difference.total_seconds() * self.TIMEFACTOR
        return self.timestamp + datetime.timedelta(seconds=new_secs)

    def save(self, *args, **kwargs):
        """Overriden save method"""
        if self.timestamp is None:
            self.timestamp = datetime.datetime.now()

        super(Game, self).save(*args, **kwargs)

        # make sure host is a player
        if not self.players.filter(id=self.host.id).exists():
            self.add_player(self.host)

    def is_over(self):
        """Return true iff game is over

        Game Over means all players have acheieve all goals"""
        goals = Goal.objects.filter(game=self)

        for goal in goals:
            for player in self.players.all():
                if not goal.was_achieved_by(player):
                    return False
        return True


    @transaction.commit_on_success
    def update(self, profile, now=None):
        """Should be called by views"""
        profile_ticket = profile_airport = None
        winners_before = self.winners()
        now = now or self.time
        if self.state == 0:
            return (self.timestamp, None, None)

        if self.is_over():
            self.end()
            return (self.timestamp, None, None)

        goals = Goal.objects.filter(game=self).distinct()

        # update player & goals
        for player in self.players.all().distinct():
            previous_ticket = player.ticket
            airport, ticket = player.location(now, self)
            if player == profile:
                profile_airport, profile_ticket = airport, ticket
            for goal in goals:
                if goal.was_achieved_by(player):
                    continue
                if airport and airport.city == goal.city:
                    ach = Achiever.objects.get(profile=player, goal=goal)
                    ach.timestamp = previous_ticket.arrival_time
                    ach.save()
                    Message.announce(player, '%s has achieved %s'
                            % (player.user.username, goal))
                    break
                else:
                    break

        winners = self.winners()
        if not winners_before and winners:
            if len(winners) == 1:
                Message.broadcast('%s has won %s' % (winners[0].user.username,
                    self), self)
            else:
                Message.broadcast('%s: %s-way tie for 1st place' % (self,
                    len(winners)), self)
                for winner in winners:
                    Message.broadcast('%s is a winner!' %
                            winner.user.username, self)

        # if all players have achieved all goals, end the game
        if self.is_over():
            #Message.broadcast('Game Over!', self)
            self.end()

        return (now, profile_airport, profile_ticket)

    def winners(self):
        """Return the winners of the game or [] if there are no
        winners(yet)"""

        if self.state == -1:
            # no winner if game hasn't started yet
            return []

        # get the last goal
        last_goal = Goal.objects.filter(game=self).order_by('-order')[0]
        achievers = Achiever.objects.filter(goal=last_goal,
                timestamp__isnull=False).order_by('timestamp')
        if not achievers.exists():
            return None
        return [i.profile for i in achievers]

    @classmethod
    def get_or_create(cls, host):
        """Get or create a game:

        Returns the latest games that host is player in, if that game has
        not ended.  Else creates and returns a new game.
        Uses the same 2-tuple format as the Django model manager method

        """
        created = False
        #open_games = cls.objects.filter(


class Goal(models.Model):
    """Goal cities for a game"""
    city = models.ForeignKey(City)
    game = models.ForeignKey(Game)
    order = models.IntegerField()
    achievers = models.ManyToManyField(UserProfile, through='Achiever')

    def __unicode__(self):
        return u'%s: Goal %s/%s for game %s' % (
                self.city.name,
                self.order,
                self.game.goals.all().count(),
                self.game.pk)

    def was_achieved_by(self, player):
        """Return True iff player has achieved goal"""
        return Achiever.objects.filter(
                profile=player,
                goal=self,
                game=self.game,
                timestamp__isnull=False).exists()

    class Meta:
        """metadata"""
        ordering = ['game', 'order']

class Achiever(models.Model):
    """Users who have achieved a goal"""
    profile = models.ForeignKey(UserProfile)
    goal = models.ForeignKey(Goal)
    game = models.ForeignKey(Game)
    timestamp = models.DateTimeField(null=True)


    def save(self, *args, **kwargs):
        """Overriden save() method"""
        if self.goal:
            self.game = self.goal.game

        super(Achiever, self).save(*args, **kwargs)

class Purchase(models.Model):
    """Table used to track purchases"""
    profile = models.ForeignKey(UserProfile)
    game = models.ForeignKey(Game, related_name='+')
    flight = models.ForeignKey(Flight, related_name='+')

    def __unicode__(self):
        return u'%s purchased flight %s from %s to %s' % (
                profile.user.username,
                flight.origin.code,
                flight.destination.code
        )
