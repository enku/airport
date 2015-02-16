"""Models for the airport django app"""
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from random import randint, sample, shuffle

from django.contrib.auth.models import User
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.template.defaultfilters import date, escape

from . import logger
from .conf import settings

BOARDING = timedelta(minutes=settings.MINUTES_BEFORE_BOARDING)


class AirportModel(models.Model):

    """Base class for airport models"""
    creation_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class City(AirportModel):

    """A City"""
    name = models.CharField(max_length=50, unique=True)
    image = models.CharField(max_length=300, null=True)
    latitude = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    longitude = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    def __str__(self):
        return self.name

    def distance_from(self, city):
        """Return the distance (km) from *self* to *city*"""
        return self.distance_from_coordinates((city.latitude, city.longitude))

    def distance_from_coordinates(self, coordinates):
        """Return the distance (km) from *self* to *coordinates*)

        *coordinates shall be a 2-tuple
        """
        latitude, longitude = coordinates
        # using haversine
        lat1, lon1, lat2, lon2 = map(radians, [self.latitude,
                                               self.longitude,
                                               latitude,
                                               longitude])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) *
             sin(dlon / 2) ** 2)
        c = 2 * asin(sqrt(a))
        km = 6367 * c
        return km

    @classmethod
    def closest_to(cls, coordinates):
        """Return the City closest to coordinates"""
        # I should be using the db's geo stuff for this, but I'm keeping it
        # database-agnostic
        cities = cls.objects.all()
        cities = list(cities)

        cities.sort(key=lambda x: x.distance_from_coordinates(coordinates))
        return cities[0] if cities else None

    @classmethod
    def get_flight_time(cls, source, destination, speed):
        """Return the time, in minutes, it takes to fly from *source* to
        *destination* at speed *speed*"""
        if isinstance(source, (Airport, AirportMaster)):
            source = source.city
        if isinstance(destination, (Airport, AirportMaster)):
            destination = destination.city
        distance = source.distance_from(destination)
        flight_time = distance / speed
        return flight_time

    def airports(self):
        """Return a qs of AirportMasters in this city"""
        a = AirportMaster.objects.filter(city=self)
        return a

    class Meta:

        """metadata"""
        verbose_name_plural = 'cities'


class AirportMaster(AirportModel):

    """An Airport"""
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=4, unique=True)
    city = models.ForeignKey(City)

    def __str__(self):
        return 'Master Airport: {name}'.format(name=self.name)


class Airport(AirportModel):

    """Airports associated with a particular game"""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=4)
    city = models.ForeignKey(City)
    game = models.ForeignKey('Game', related_name='airports')
    destinations = models.ManyToManyField('self', null=True, blank=True,
                                          symmetrical=True)

    def __str__(self):
        aiports_per_city = Airport.objects.filter(game=self.game,
                                                  city=self.city).count()
        if aiports_per_city > 1:
            return '{city} {code}'.format(city=self.city, code=self.code)
        return self.city.name

    @classmethod
    def copy_from_master(cls, game, master):
        """Copy airport from the AirportMaster into *game* and populate it
        with destinations"""
        airport = cls()
        airport.name = master.name
        airport.code = master.code
        airport.game = game
        airport.city = master.city
        airport.save()

        return airport

    def next_flights(self, now, future_only=False, auto_create=True):
        """Return next Flights out from *self*, creating new flights if
        necessary.  Return a list of flights ordered by destination city
        name

        If *future_only* is True, only return future flights.  By default,
        will also return Flights that have already departed.  This is so
        the views that need flights can also display historical flights.
        If you only want future flights, pass "future_only=True"

        If *auto_create* is True (default), automagically create fututure
        flights
        """
        game = self.game
        future_flights = self.flights.filter(game=game, depart_time__gt=now)

        if not future_flights.exists() and auto_create:
            self.create_flights(now)

        flights = game.flights.filter(origin=self)
        if future_only:
            flights = flights.filter(depart_time__gt=now)
        flights = list(flights.order_by('-depart_time')[:10])

        flights.sort(key=lambda x: x.destination.city.name)
        return flights

    def clean(self):
        """validation"""
        # airport destinations can't be in the same city
        if self.destinations.filter(city=self.city).exists():
            raise ValidationError(
                'Airport cannot have itself as a destination.')

    def next_flight_to(self, city, now):
        """Return the next flight to *city* or None"""
        if isinstance(city, Airport):
            city = city.city
        next_flights = self.next_flights(now, future_only=True,
                                         auto_create=False)
        next_flights = [i for i in next_flights if i.depart_time >= now and
                        i.destination.city == city]
        next_flights.sort(key=lambda flight: flight.depart_time)

        if next_flights:
            return next_flights[0]
        return None

    def create_flights(self, now):
        """Create some flights starting from *now*"""
        game = self.game
        cushion = 20  # minutes

        flight_ids = []
        for destination in self.destinations.distinct():
            flight_time = City.get_flight_time(self.city,
                                               destination.city,
                                               Flight.cruise_speed)

            if settings.SCALE_FLIGHT_TIMES:
                flight_time = game.scale_flight_time(flight_time)
            else:
                if settings.MIN_FLIGHT_TIME is not None:
                    flight_time = max(flight_time, settings.MIN_FLIGHT_TIME)
                if settings.MAX_FLIGHT_TIME is not None:
                    flight_time = min(flight_time, settings.MAX_FLIGHT_TIME)

            flight = Flight.objects.create(
                game=game,
                origin=self,
                destination=destination,
                depart_time=(timedelta(minutes=cushion) +
                             random_time(now)),
                flight_time=flight_time)
            flight_ids.append(flight.id)
        return Flight.objects.filter(id__in=flight_ids)

    def get_destinations(self, dest_count):
        """Get the destinations for airport. rules are:

        * Can't have more than *dest_count* destinations
        * destination airports can't add more than *dest_count*
        * destination can't be in the same city
        """
        # if dest_count < 1:
        #    raise ValueError("Can't have < 1 destinations on an airport")

        queryset = Airport.objects.exclude(city=self.city)
        queryset = queryset.filter(game=self.game)
        queryset = queryset.exclude(id=self.id)
        queryset = queryset.annotate(num_dest=models.Count('destinations'))
        queryset = queryset.filter(num_dest__lt=dest_count)

        try:
            return sample(set(queryset), dest_count)
        except ValueError:
            # try again
            return self.get_destinations(dest_count - 1)

    def save(self, *args, **kwargs):
        super(Airport, self).save(*args, **kwargs)
        self.clean()


class FlightManager(models.Manager):

    """we manage flights"""

    def random_flight_number(self, game):
        """return a random number, not already a flight number for *game*"""
        flights = self.filter(game=game).count()
        return flights % 9900 + 100

    def arrived_but_not_flagged(self, game, now=None):
        """Return a qs of Flights that (should have) arrived but do not have
        their state set to 'Arrived'
        """
        now = now or game.time

        flights = Flight.objects.filter(game=game)
        flights = flights.filter(arrival_time__lte=now)
        flights = flights.exclude(state='Arrived')
        return flights

    def in_flight(self, game, now=None):
        """Return a queryset of flights currently in the air"""
        now = now or game.time

        flights = self.filter(game=game)
        flights = flights.filter(depart_time__lt=now)
        flights = flights.filter(arrival_time__gt=now)
        flights = flights.exclude(state='Cancelled')
        return flights


class Flight(AirportModel):

    """a flight from one airport to another"""
    # fields ###
    game = models.ForeignKey('Game', null=False, related_name='flights')
    number = models.IntegerField(editable=False)
    origin = models.ForeignKey(Airport, related_name='flights')
    destination = models.ForeignKey(Airport, related_name='+')
    depart_time = models.DateTimeField()
    flight_time = models.IntegerField()
    arrival_time = models.DateTimeField()  # caculated field
    state = models.CharField(max_length=20, default='On Time')
    full = models.BooleanField(default=False)
    objects = FlightManager()

    cruise_speed = settings.CRUISE_SPEED

    def in_flight(self, now):
        """Return true if flight is in the air"""
        if self.state == 'Cancelled':
            return False

        if self.depart_time <= now <= self.arrival_time:
            return True

        return False

    def has_landed(self, now):
        """Return True iff flight has landed"""

        if self.state == 'Cancelled':
            return False

        return (now >= self.arrival_time)

    @property
    def cancelled(self):
        """Return True iff a flight is cancelled"""
        return self.state == 'Cancelled'

    def cancel(self, now):
        """Cancel a flight. In-flight flights (obviously) can't be
        cancelled"""

        if not self.in_flight(now):
            self.state = 'Cancelled'
            self.save()

            # if any players have tickets on this flight, they need to be
            # revoked
            for passenger in self.passengers.all():
                passenger.ticket = None
                passenger.save()

        else:
            raise self.AlreadyDeparted(
                'In-progress flight cannot be cancelled')

    def delay(self, timedelta, now=None):
        """Delay the flight by *timedelta*"""
        if now is None:
            now = self.game.time

        if self.in_flight(now) or self.has_landed(now):
            raise self.AlreadyDeparted()

        if self.state == 'Cancelled':
            raise self.Finished()

        self.depart_time = self.depart_time + timedelta
        self.state = 'Delayed'
        self.save()

    def get_remarks(self, now=None):
        """Return textual remark about a ticket

        Text can be:
        "Cancelled" for cancelled tickets
        "Delayed" for Delayed flights
        "Departed" if the flight is currently in the air
        "Arrived" if the flight has arrived at its destination
        """
        now = now or self.game.time
        suffix = ''
        full = '/Full' if self.full else ''
        origin = self.origin
        destination = self.destination

        if not origin.destinations.filter(id=destination.id).exists():
            suffix = '*'

        state = self.state

        if state == 'Cancelled':
            return state

        if state == 'Delayed':
            return state + full

        if self.in_flight(now):
            if self.state != 'Departed':
                self.state = 'Departed'
                self.save()
            return 'Departed' + suffix

        if self.arrival_time <= now:
            return 'Arrived' + suffix

        if self.depart_time - BOARDING < now:
            return 'Boarding' + full

        return 'On Time' + full

    def buyable(self, player, now):
        """Return True if a ticket is buyable else return False"""

        return (
            not self.cancelled
            and not self.full
            and self.depart_time > now
            and self != player.ticket
        )

    def to_dict(self, now):
        """Helper method to return Flight as a json-serializable dict"""
        status = self.get_remarks(now)

        origin = {
            'airport': str(self.origin),
            'city': self.origin.city.name,
            'code': self.origin.code,
        }

        dest = {
            'airport': str(self.destination),
            'city': self.destination.city.name,
            'code': self.destination.code,
        }

        return {
            'number': self.number,
            'id': self.pk,
            'depart_time': date(self.depart_time, 'P'),
            'arrival_time': date(self.arrival_time, 'P'),
            'origin': origin,
            'destination': dest,
            'status': status,
        }

    def elapsed(self):
        """Return a timedelta of time elapsed (would have elapsed) since
        from game creation_time to the flight arrival time"""
        arrived = self.depart_time + timedelta(minutes=self.flight_time)
        game_create_time = self.game.creation_time
        elapsed_time = arrived - game_create_time
        # chop off microseconds
        elapsed_time = timedelta(elapsed_time.days, elapsed_time.seconds)
        return elapsed_time

    @property
    def passengers(self):
        """Return a qs of passengers (Player) on this *Flight*"""
        return Player.objects.filter(ticket=self)

    def save(self, *args, **kwargs):
        """Overriden .save() method for Flights"""
        # we need a unique fligth # for this game
        if not self.number:
            self.number = Flight.objects.random_flight_number(self.game)

        self.arrival_time = (self.depart_time
                             + timedelta(minutes=self.flight_time))

        return super(Flight, self).save(*args, **kwargs)

    def clean(self, *_args, **_kwargs):
        """Validate the model"""
        # Origin can't also be desitination
        if self.origin == self.destination:
            raise ValidationError('Origin and destination cannot be the same')

        if self.origin.desitinations.filter(id=self.destination.id).exists():
            raise ValidationError('%s not accessible from %s' %
                                  (self.destination.code, self.origin.code))

    # Special Methods ###
    def __str__(self):
        return '{flight} from {origin} to {dest} departing at {time}'.format(
            flight=self.number,
            origin=self.origin.code,
            dest=self.destination.code,
            time=date(self.depart_time, 'P'))

    # Exceptions ###
    class BaseException(Exception):

        """Base Exception for scheduling/ticketing errors"""
        pass

    class AlreadyDeparted(BaseException):

        """A Flight is already departed"""
        pass

    class Full(Exception):

        """The flight is full"""
        pass

    class NotAtDepartingAirport(BaseException):

        """Exception raised when a player attempts to purchase a flight at a
        different airport than they are located in"""
        pass

    class Finished(BaseException):

        """Flight has already landed or is cancelled"""
        pass

    # Meta ###
    class Meta:

        """metadata"""
        ordering = ['depart_time']


def random_time(now, maximum=40):
    """Helper function, return a random time in the future (from *now*)
    with a maximium of *maximum* minutes in the future"""

    flight_time = randint(0, maximum)
    return now + timedelta(minutes=flight_time)


class PlayerManager(models.Manager):
    def winners(self, game):
        """Return the winners of the game."""

        if game.state == game.NOT_STARTED:
            # no winner if game hasn't started yet
            return self.none()

        # get the last goal
        last_goal = Goal.objects.filter(game=game).order_by('-order')[0]
        stats = last_goal.stats()
        times = [stats[i] for i in stats if stats[i]]
        if not times:
            return self.none()
        times.sort()
        winning_time = times[0]
        return self.filter(
            achievement__goal=last_goal,
            achievement__timestamp=winning_time
        )

    def finishers(self, game):
        """Return the queryset of players who have finished the game"""
        last_goal = Goal.objects.filter(game=game).order_by('-order')[0]
        stats = last_goal.stats()
        finishers = [i for i in stats if stats[i] is not None]
        return self.filter(id__in=[i.id for i in finishers])

    @transaction.atomic
    def get_or_create_ai_player(self, game):
        """Create an AI player and attach to game."""
        # the reason why game is required is why would you don't need to create
        # an AI player anyway w/o a game associated with it

        # if game already has an AI player, just return that
        try:
            return game.players.filter(ai_player=True).distinct()[0]
        except IndexError:
            pass

        # See if there are any available players
        players = self.filter(ai_player=True)
        players = players.order_by('?')
        for player in players:
            if player.current_game is None:
                break
        else:
            # If none, create one
            pcount = self.filter(ai_player=True).count()
            username = '{0}{1}'.format(settings.AI_USERNAMES, pcount + 1)
            user = User.objects.create_user(username=username)
            player = self.create(user=user, ai_player=True)

        game.add_player(player)
        return player


class Player(AirportModel):

    """Profile for players"""
    user = models.ForeignKey(User, related_name='player')
    airport = models.ForeignKey(Airport, null=True, blank=True)
    ticket = models.ForeignKey(Flight, null=True, blank=True,
                               related_name='passengers')
    ai_player = models.BooleanField(default=False)
    objects = PlayerManager()

    def __str__(self):
        return 'Player {0}'.format(self.user.username)

    @property
    def games(self):
        """Games this player has played"""
        return self.game_set.distinct()

    def finished(self, game):
        """Return if player finished game"""
        return Player.objects.finishers(game).filter(pk=self.pk).exists()

    @property
    def current_game(self):
        """Return player's current open game or None if there is none"""
        try:
            last_game = self.games.order_by('-id')[0]
            if not self.finished(last_game):
                return last_game
        except IndexError:
            pass
        return None

    @property
    def current_state(self):
        """Return one of:
            'hosting' when player is hosting an unstarted game
            'waiting' when player has joined an unstarted game
            'open' when player hasn't joined a game
            'playing' when player is in started game
        """
        game = self.current_game
        if game is None:
            return 'open'

        if game.state == game.NOT_STARTED:
            if game.host == self:
                return 'hosting'
            return 'waiting'

        if game.state == game.IN_PROGRESS:
            return 'playing'

        # should never reach here, but...
        return 'open'

    @property
    def goals(self):
        """Return a qs of all goals acquired"""
        return Goal.objects.filter(
            achievers=self,
            achievement__timestamp__isnull=False,
        )

    def next_goal(self, game):
        """Return the next required goal (Achievment) for game.

        If player has achieved all goals, return None.
        """
        query = Achievement.objects
        achievements = query.filter(player=self, game=game, timestamp=None)
        achievements = achievements.order_by('goal__order')
        if achievements.exists():
            return achievements[0]
        return None

    @property
    def tickets(self):
        """Return qs of Purchases"""
        return self.purchase_set.all()

    def location(self, now):
        """Update and return player's current location info

        info is a tuple of (Airport or None, Flight or None)

        This updates *ticket* and *airport* properties and returns either a
        *Flight* object or an *Airport* object depending on whether the Player
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
                    return (self.airport, None)

        self.save()
        return (self.airport, self.ticket)

    def purchase_flight(self, flight, now):
        """Purchase a flight.  User must be at the origin airport and must be a
        future flight"""

        if flight.game.state == flight.game.PAUSED:
            raise flight.game.Paused('Cannot purchase tickets while '
                                     'game is paused')

        if flight.full:
            raise flight.Full('This flight is full')

        if self.ticket and self.ticket.in_flight(now):
            raise flight.AlreadyDeparted(
                'Cannot purchase a flight while in flight')

        if self.airport != flight.origin:
            raise flight.NotAtDepartingAirport(
                'Must be at the departing airport ({airport} to purchase'
                'flight'.format(airport=flight.origin))

        if flight.depart_time <= now:
            raise flight.AlreadyDeparted('Flight already departed')

        self.ticket = flight
        self.save()

    def is_playing(self, game):
        """Return True if player is a player in *game* else False"""
        return game.players.filter(id=self.id).exists()

    def needs_goal(self, game, city):
        """If the user needs this city as a goal, return the Achievement model.

        Else return False.
        """
        try:
            ach = Achievement.objects.get(player=self,
                                          game=game,
                                          goal__city=city)
        except Achievement.DoesNotExist:
            return False

        if ach.timestamp is None:
            return ach
        return False

    def in_limbo(self, game, now=None):
        """Return True if player is in 'limbo'."""
        ticket = self.ticket
        airport = self.airport

        # Not at an airport but has no ticket (not in flight)
        if not any([ticket, airport]):
            return True

        # Has a ticket, the flight has landed but he's not at an airport
        if ticket and not airport and ticket.has_landed(now or game.time):
            return True

        return False

    def info(self, game=None, now=None, redirect=None):
        """Return a json-able dict about the current info of the player.

        This should be equivalent to what the views.info view used to do, but
        is now put on the Player since that view is gone and we now push
        the data to the browser via websockets.

        "redirect", if passed, should be a URL string informing the player's
        browser to redirect to said URL.
        """
        states = ['New', 'Finished', 'Started', 'Paused']
        game = game or self.current_game
        now = now or game.time
        finished = self.finished(game)
        stats = game.stats()
        goal_list = []
        nf_list = []
        in_flight = self.ticket.in_flight(now) if self.ticket else False
        percentage = 100 if not in_flight else int(
            (now - self.ticket.depart_time).total_seconds()
            / 60.0 / self.ticket.flight_time * 100)

        airport = self.airport if self.airport else self.ticket.destination
        next_flights = airport.next_flights(now, auto_create=False)

        for next_flight in next_flights:
            nf_dict = next_flight.to_dict(now)
            buyable = False if finished else next_flight.buyable(self, now)
            nf_dict['buyable'] = buyable
            nf_list.append(nf_dict)

        for goal in Goal.objects.filter(game=game):
            achieved = goal.achievers.filter(
                id=self.id, achievement__timestamp__isnull=False).exists()
            goal_list.append([goal.city.name, achieved])

        # city name
        if self.airport:
            city = self.airport.city.name
        elif self.ticket:
            city = self.ticket.destination.city.name
        else:
            city = None

        # airport name
        airport = self.airport
        airport = airport.name if airport else self.ticket.origin.name
        ticket = None if not self.ticket else self.ticket.to_dict(now)

        info_dict = {
            'time': date(now, 'P'),
            'game': game.pk,
            'game_state': states[game.state + 1],
            'airport': airport,
            'city': city,
            'ticket': ticket,
            'next_flights': nf_list,
            'message_id': None,
            'in_flight': in_flight,
            'finished': finished,
            'percentage': percentage,
            'goals': goal_list,
            'stats': stats,
            'notify': None,
            'player': self.user.username
        }

        if redirect:
            info_dict['redirect'] = redirect
        return info_dict

    def game_info(self):
        # TODO: Document
        game = self.current_game
        state = self.current_state

        if game:
            finished_current = self.finished(game)
            current_game = game.pk
        else:
            current_game = None
            finished_current = False

        data = {
            'current_game': current_game,
            'current_state': state,
            'finished_current': finished_current
        }
        return data

    def make_move(self, game=None, now=None):
        """AI make a move.  Assume we are in a game."""
        assert self.ai_player
        game = game or self.current_game
        assert game

        # First, determine if we even need to/can make a move
        # Thank goodness for short-circuiting
        no_move = game is None
        no_move = no_move or self.current_state != 'playing'
        no_move = no_move or self.ticket is not None
        no_move = no_move or game.state == game.GAME_OVER
        no_move = no_move or self.finished(game)

        if no_move:
            return

        now = now or game.time
        airport = self.airport
        assert airport

        ach = self.next_goal(game)
        goal = ach.goal

        # If our next goal is at this airport and the ticket is buyable, buy it
        next_flight = airport.next_flight_to(goal.city, now)
        if next_flight and next_flight.buyable(self, now):
            self.purchase_flight(next_flight, now)
            return

        # Else figure out the next flights.
        next_flights = airport.next_flights(
            now, future_only=True, auto_create=False)

        # If there is only one flight. Take it
        if len(next_flights) == 1 and next_flights[0].buyable(self, now):
                self.purchase_flight(next_flights[0], now)
                return

        # Exclude the airport we just came from
        last_purchases = Purchase.objects.filter(player=self, game=game)
        try:
            last_purchase = last_purchases.order_by('-flight__arrival_time')[0]
        except IndexError:
            pass
        else:
            origin = last_purchase.flight.origin
            next_flights = [i for i in next_flights if i.destination != origin]

        if not next_flights:
            return

        next_flights.sort(key=lambda x: x.arrival_time)
        for next_flight in next_flights:
            if next_flight.buyable(self, now):
                self.purchase_flight(next_flight, now)
                return

    def save(self, *args, **kwargs):
        new_player = not self.id

        super(Player, self).save(*args, **kwargs)
        if new_player:
            msg = 'Welcome to {}!'.format(settings.GAME_NAME)
            Message.objects.send(self, msg)

    @property
    def username(self):
        return self.user.username
User.player = property(lambda u: Player.objects.get_or_create(user=u)[0])


class MessageManager(models.Manager):
    def broadcast(self, text, game=None, message_type='DEFAULT',
                  finishers=False):
        """Send a message to all players in *game*"""
        logger.info('Game {0}: BROADCAST: {1}'.format(game, text))
        messages = []

        if game:
            players = Player.objects.filter(game=game)
            players = players.exclude(ai_player=True).distinct()
            if not finishers:
                to_exclude = Player.objects.finishers(game)
                to_exclude = to_exclude.values_list('pk', flat=True)
                players = players.exclude(pk__in=to_exclude)
        else:
            players = Player.objects.exclude(ai_player=True)

        for player in players:
            messages.append(self.create(player=player, text=text,
                                        message_type=message_type))
        return messages

    def announce(self, announcer, text, game=None, message_type='DEFAULT',
                 finishers=False):
        """Sends a message to all player but *announcer*"""
        logger.info('Game {0}: ANNOUNCE: {1}'.format(game, text))
        messages = []

        if isinstance(announcer, User):
            # we want the Player, but allow the caller to pass User as
            # well
            announcer = announcer.player

        if game:
            players = Player.objects.filter(game=game).distinct()
            players = players.exclude(ai_player=True)
            if not finishers:
                to_exclude = Player.objects.finishers(game)
                to_exclude = to_exclude.values_list('pk', flat=True)
                players = players.exclude(pk__in=to_exclude)
        else:
            players = Player.objects.exclude(ai_player=True)

        for player in players.exclude(id=announcer.id).distinct():
            messages.append(self.create(player=player, text=text,
                                        message_type=message_type))
        return messages

    def send(self, player, text, message_type='DEFAULT'):
        """Send a unicast message to *player* return the Message object"""
        if isinstance(player, User):
            # we want the Player, but allow the caller to pass User
            # as well
            player = player.player

        if player.ai_player:
            return

        logger.info('MESSAGE({0}): {1}'.format(player.username, text))

        return self.create(player=player, text=text, message_type=message_type)

    def get_messages(self, request, last_message=0, read=True, old=False):
        """Get messages for *request.user* (as a list)
            if *read*=True (default), mark the messages as read"""

        user = request.user

        if old:
            messages_qs = self.filter(player=user.player,
                                      id__gt=last_message)
        else:
            messages_qs = self.filter(player=user.player,
                                      id__gt=last_message, read=False)
        messages_qs = messages_qs.order_by('-id')
        messages = list(messages_qs)[:settings.MAX_SESSION_MESSAGES]
        for message in messages:
            message.new = not message.read
        if read:
            messages_qs.update(read=True)

        return messages

    def get_latest(self, player, read=False):
        """Get the latest message for a user.  By default, does not mark
        the message as read"""
        if isinstance(player, User):
            player = player.player

        messages = self.filter(player=player).order_by('-creation_time')
        if messages.exists():
            message = messages[0]
        else:
            message = None

        if read and message:
            message.read = True
            message.save()

        return message

    pass


class Message(AirportModel):

    """Messages for players"""
    text = models.CharField(max_length=255)
    player = models.ForeignKey(Player, related_name='messages')
    read = models.BooleanField(default=False)
    message_type = models.CharField(max_length=32, default='DEFAULT')
    objects = MessageManager()

    def __str__(self):
        return self.text

    def to_dict(self):
        """
        Return Message as a Python dict.
        """
        return {
            'id': self.pk,
            'text': self.text,
            'type': self.message_type,
        }

    def mark_read(self):
        self.read = True
        self.save()

announce = Message.objects.announce
broadcast = Message.objects.broadcast


class GameManager(models.Manager):

    """We manage Games"""

    def create_game(self, host, goals, airports, density=5, ai_player=True,
                    start=None):
        """Create a new *Game*"""
        master_airports = list(AirportMaster.objects.distinct())
        shuffle(master_airports)

        game = Game()

        if isinstance(host, User):
            host = host.player
        game.host = host
        game.state = Game.NOT_STARTED
        game.save()

        # start airport
        if start is None:
            master = master_airports[0]
        else:
            master = start
        start_airport = Airport()
        start_airport.name = master.name
        start_airport.code = master.code
        start_airport.city = master.city
        start_airport.game = game
        start_airport.save()

        game.start_airport = start_airport
        game.save()

        # add other airports
        for i in range(1, airports):
            master = master_airports[i]
            airport = Airport.copy_from_master(game, master)

        # populate the airports with destinations
        for airport in game.airports.distinct():
            new_destinations = airport.get_destinations(density)
            for destination in new_destinations:
                if airport.destinations.count() >= density:
                    break
                airport.destinations.add(destination)

        # record min/max distances
        game.min_distance, game.max_distance = game.get_extremes()
        game.save()

        # add goals
        current_airport = game.start_airport
        goal_airports = []
        for i in range(1, goals + 1):
            direct_flights = current_airport.destinations.distinct()
            dest = Airport.objects.filter(game=game)
            dest = dest.exclude(id=current_airport.id)
            dest = dest.exclude(city__in=[j.city for j in goal_airports])
            dest = dest.exclude(id__in=[j.id for j in direct_flights])
            dest = dest.order_by('?')
            dest = dest[0]

            goal = Goal()
            goal.city = dest.city
            goal.game = game
            goal.order = i
            goal.save()
            goal_airports.append(dest)

            current_airport = dest

        game.add_player(host)

        msg = '{0} has created {1}.'
        msg = msg.format(host.user.username, game)
        broadcast(msg, message_type='NEW_GAME')

        if ai_player:
            Player.objects.get_or_create_ai_player(game)

        return game

    def finished_by(self, player):
        """Return qs of games finished by player"""
        finished = []
        games_played = self.filter(players=player).distinct()
        for game in games_played:
            if player.finished(game):
                finished.append(game.pk)
        return self.filter(pk__in=finished)

    def won_by(self, player):
        """Return qs of games won"""
        # TODO: There has got to be a better way to do this
        winner_ids = set()
        for game in self.finished_by(player):
            last_goal = Goal.objects.filter(game=game).order_by('-order')[0]
            winner_time = Achievement.objects.filter(
                goal=last_goal,
                timestamp__isnull=False
            ).order_by('timestamp')[0].timestamp
            winners = Achievement.objects.filter(
                goal=last_goal,
                timestamp=winner_time
            )
            for winner in winners:
                if winner.player == player:
                    winner_ids.add(game.id)
                    break
        return Game.objects.filter(id__in=winner_ids)


class Game(AirportModel):

    """This is a game.  A Game is hosted and has it's own game time and
    players and stuff like that.  A Game is either not started, in progress or
    ended.

    A game has goals, which is a list of airport (in order) that each player
    must go to.  The Game keeps track of which players have achieved which
    goals.

    The Game is the God of Airport"""
    NOT_STARTED, GAME_OVER, IN_PROGRESS, PAUSED = -1, 0, 1, 2
    STATE_CHOICES = (
        (-1, NOT_STARTED),
        (0, GAME_OVER),
        (1, IN_PROGRESS),
        (2, PAUSED))

    TIMEFACTOR = settings.TIMEFACTOR

    host = models.ForeignKey(Player, related_name='+')
    players = models.ManyToManyField(Player, null=True, blank=True,
                                     through='Achievement')
    state = models.SmallIntegerField(choices=STATE_CHOICES, default=-1)
    goals = models.ManyToManyField(City, through='Goal')
    # airports = models.ManyToManyField(Airport)
    start_airport = models.ForeignKey(Airport, null=True, related_name='+')
    timestamp = models.DateTimeField(auto_now_add=True)
    pausestamp = models.DateTimeField(null=True)
    pause_time = models.IntegerField(default=0)
    min_distance = models.IntegerField(null=True)
    max_distance = models.IntegerField(null=True)
    objects = GameManager()

    def __init__(self, *args, **kwargs):
        from airport.monkeywrench import MonkeyWrenchFactory

        super(Game, self).__init__(*args, **kwargs)
        self.mwf = MonkeyWrenchFactory()

    def __str__(self):
        return 'Game {}'.format(self.pk)

    @classmethod
    def open_games(cls):
        """Return the set of non-closed games."""
        return cls.objects.exclude(state=cls.GAME_OVER)

    def begin(self):
        """start the game"""
        for player in self.players.distinct():
            player.airport = self.start_airport
            player.game = self
            player.save()

        self.state = self.IN_PROGRESS
        self.timestamp = datetime.now()
        self.save()
        announce(self.host, 'Game {0} has begun'.format(self.pk))

    def end(self):
        """End the Game"""
        if self.state == self.GAME_OVER and self.timestamp:
            # We've already ended this game(?)
            return

        self.state = self.GAME_OVER
        self.timestamp = datetime.now()
        self.save()
        for player in self.players.distinct():
            player.game = None
            player.save()

        msg = '{0} has ended!'.format(self)
        broadcast(msg, finishers=True)

    def add_player(self, player):
        """Add player to profile if game hasn't ended"""
        if self.state == self.GAME_OVER:
            logger.info('{0}: game over, cannot add players'.format(self))
            return

        if player in self.players.distinct():
            logger.info('{0}: already in players'.format(self))
            return

        # This should never happen at the UI level, but we check anyway
        # Make sure a player currently in an active game can't be added to
        # this one.  If they're hosting this game, remove it
        current_game = player.current_game
        if current_game and current_game != self:
            if current_game.state != Game.GAME_OVER:
                if not self.players.exists() and self.host == player:
                    self.delete()
                raise self.AlreadyInGame('%s is already in an active game'
                                         % player.user)

        # This is a pain in the ass to do, basically we need to create an
        # Achievement model for each goal
        for goal in Goal.objects.filter(game=self):
            Achievement.objects.create(
                player=player,
                goal=goal,
                game=self)

        # put the player at the starting airport and take away their
        # tickets
        player.ticket = None
        player.airport = self.start_airport
        player.save()

        # Send out an announcement
        if player != self.host:
            msg = '{0} has joined {1}.'
            msg = msg.format(player.user.username, self)
            broadcast(msg, self, message_type='PLAYERACTION')
        # put the player at the starting airport and take away their
        # tickets
        player.ticket = None
        player.airport = self.start_airport
        player.save()

    def remove_player(self, player):
        """Remove a player from the game... *player* can be a User or
        Player model.

        This method does not check that the user is actually in the game.
        If the user is not a game player, then it fails silently"""
        if isinstance(player, User):
            player = player.player
        achievements = Achievement.objects.select_for_update()
        achievements = achievements.filter(player=player, game=self)
        # bye!
        achievements.delete()

    @property
    def time(self):
        """Return current game time"""
        if self.state == self.PAUSED:
            now = self.pausestamp
        else:
            now = datetime.now()

        now = now - timedelta(seconds=self.pause_time)

        if hasattr(self, 'gettime'):
            # this can monkey-patched on the instance for debugging/testing
            return self.gettime()

        # dunno if this is even needed anymore
        if self.state not in (self.PAUSED, self.IN_PROGRESS):
            return now

        difference = now - self.timestamp
        new_secs = difference.total_seconds() * self.TIMEFACTOR
        return self.timestamp + timedelta(seconds=new_secs)

    def save(self, *args, **kwargs):
        """Overriden save method"""
        new_game = self.pk is None

        if self.timestamp is None:
            self.timestamp = datetime.now()

        super(Game, self).save(*args, **kwargs)

        # make sure host is a player
        if new_game and not self.players.filter(id=self.host.id).exists():
            self.add_player(self.host)

    def pause(self):
        """Pause the game"""
        if self.state == self.IN_PROGRESS:
            now = datetime.now()
            self.state = self.PAUSED
            self.pausestamp = now
            self.save()

    def resume(self):
        """Resume a paused game"""
        if self.state == self.PAUSED:
            self.pause_time = (
                self.pause_time
                + (datetime.now() - self.pausestamp).total_seconds())
            self.state = self.IN_PROGRESS
            self.pausestamp = None
            self.save()

    def is_over(self):
        """Return true iff game is over

        Game Over means all players have acheieve all goals"""
        players = self.players.distinct()

        # if there are no players, it's over
        if players.count() == 0:
            return True

        goals = Goal.objects.filter(game=self)
        for goal in goals:
            for player in players:
                if not goal.was_achieved_by(player):
                    return False
        return True

    def stats(self):
        """Return a list of 2-tuples of:
            (username, goals_achieved)

        for each player of the game"""
        stats = []
        for player in self.players.distinct().order_by('user__username'):
            stats.append(
                [player.user.username, self.goals_achieved_for(player)])
        return stats

    def goals_achieved_for(self, player):
        """Return the number of goals achieved for *player*"""
        return Achievement.objects.filter(game=self, player=player,
                                          timestamp__isnull=False).count()

    def last_goal(self):
        """Return the last Goal object for this game"""
        goals = Goal.objects.filter(game=self).order_by('-order')
        return goals[0]

    def place(self, player):
        """Return what place player placed in the game or 0 if player has not
        yet finished the game"""

        if self.state == -1:
            return 0

        goals = list(Goal.objects.filter(game=self).order_by('order'))

        final_goal = goals[-1]
        final_goal_stats = final_goal.stats()
        my_finish_time = final_goal_stats[player]
        placed = 0
        if my_finish_time:
            finish_times = sorted(
                [final_goal_stats[i] for i in final_goal_stats
                 if final_goal_stats[i]]
            )
            for finish_time in finish_times:
                placed = placed + 1
                if finish_time == my_finish_time:
                    break
        return placed

    def get_extremes(self):
        """Return a tuple of min_distance, max_distance between connecting
        airports"""
        min_distance = None
        max_distance = None
        for airport in self.airports.distinct():
            for destination in airport.destinations.all():
                distance = airport.city.distance_from(destination.city)
                if min_distance is None or distance < min_distance:
                    min_distance = distance
                if max_distance is None or distance > max_distance:
                    max_distance = distance
        return min_distance, max_distance

    def scale_flight_time(self, flight_time):
        # keep within extremes of MIN_* and MAX_*. For explanation, see
        # http://goo.gl/Lex3W
        max_flight_time = settings.MAX_FLIGHT_TIME
        min_flight_time = settings.MIN_FLIGHT_TIME
        min_ = self.min_distance / Flight.cruise_speed
        max_ = self.max_distance / Flight.cruise_speed

        return (
            ((max_flight_time - min_flight_time) * (flight_time - min_))
            / (max_ - min_)) + min_flight_time

    def record_ticket_purchase(self, player, flight):
        """Add entry to Purchase table"""
        return Purchase.objects.get_or_create(
            player=player, game=self, flight=flight)

    def info(self):
        """Return a json-able dict about the current info of the game.

        This should be equivalent to what the views.games_info view used to do,
        but is now put on the Game since we now push the data to the browser
        via websockets.
        """
        states = ['New', 'Finished', 'Started', 'Paused']
        url = reverse('airport.views.games_join')
        info_dict = {
            'id': self.pk,
            'players': self.players.distinct().count(),
            'host': escape(self.host.user.username),
            'goals': self.goals.count(),
            'airports': self.airports.count(),
            'status': states[self.state + 1],
            'created': naturaltime(self.creation_time),
            'url': '{0}?id={1}'.format(url, self.pk),
        }
        return info_dict

    @classmethod
    def games_info(cls):
        """Return a list of .info()s for open games."""
        games = cls.objects.exclude(state=0)
        games = games.order_by('creation_time')
        return [i.info() for i in games]

    class BaseException(Exception):

        """Base class for Game exceptions"""
        pass

    class Paused(BaseException):

        """Exception to be passed when an action cannot be performed
        because the game is paused"""
        pass

    class NotStarted(BaseException):

        """Raised when an action is requested from a game that has not yet
        started"""
        pass

    class AlreadyInGame(BaseException):

        """Raised if a player tries to join a game but has not finished an
        active game"""
        pass


class Goal(AirportModel):

    """Goal cities for a game"""
    city = models.ForeignKey(City)
    game = models.ForeignKey(Game)
    order = models.IntegerField()
    achievers = models.ManyToManyField(Player, through='Achievement')

    def __str__(self):
        text = 'Goal {0}/{1}'
        return text.format(self.order, self.game.goals.count())

    def stars(self):
        gold_star = settings.EXTERNALS['gold_star']
        gold_star = '<img src="{0}"/>'.format(gold_star)
        return gold_star * self.order

    def was_achieved_by(self, player):
        """Return True iff player has achieved goal"""
        return Achievement.objects.filter(
            player=player,
            goal=self,
            game=self.game,
            timestamp__isnull=False).exists()

    def stats(self):
        """Return a dict of:
        stats[player] = datetime|None

        where *player* are all players for the value is the datetime the
        player finished the goal or None if player has yet to finish it
        """
        data = {}

        achievements = Achievement.objects.filter(
            goal=self,
            game=self.game).values('player_id', 'timestamp')

        for achievement in achievements:
            player = Player.objects.get(id=achievement['player_id'])
            data[player] = achievement['timestamp']

        return data

    class Meta:

        """metadata"""
        ordering = ['game', 'order']


class Achievement(AirportModel):

    """Player who have achieved a goal"""
    player = models.ForeignKey(Player)
    goal = models.ForeignKey(Goal)
    game = models.ForeignKey(Game)
    timestamp = models.DateTimeField(null=True)

    def fulfill(self, timestamp):
        self.timestamp = timestamp
        self.save()
        return self

    def save(self, *args, **kwargs):
        """Overriden save() method"""
        if self.goal:
            self.game = self.goal.game

        if self.id is not None:
            old_ach = Achievement.objects.get(id=self.id)
            if old_ach.timestamp is None:
                # send out a message
                msg = '{0} has achieved a goal: {1}'
                msg = msg.format(self.player.user.username, self.goal.stars())
                broadcast(msg, self.game, message_type='GOAL')

        super(Achievement, self).save(*args, **kwargs)


class Purchase(AirportModel):

    """Table used to track purchases"""
    player = models.ForeignKey(Player)
    game = models.ForeignKey(Game, related_name='+')
    flight = models.ForeignKey(Flight, related_name='+')

    str = '{player} purchased flight {num} from {origin} to {dest}'

    def __str__(self):
        return self.str.format(
            player=self.player.user.username,
            num=self.flight.number,
            origin=self.flight.origin.code,
            dest=self.flight.destination.code
        )
