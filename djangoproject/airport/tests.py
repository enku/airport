# -*- encoding: utf8 -*-
import datetime
import json
import random

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase

from airport  import models

def create_users(num_users):
    """create «num_users»  users and UserProfiles, return a tuple of the
    users created"""
    users = []
    for i in range(1, num_users + 1):
        user = User.objects.create_user(
            username = 'user%s' % i,
            email = 'user%s@test.com' % i,
            password = 'test'
        )
        up = models.UserProfile()
        up.user = user
        up.save()
        users.append(user)
    return tuple(users)

class AirportTest(TestCase):
    """Test Airport Model"""

    def setUp(self):
        "setup"

        # create user and game
        self.user = User.objects.create(
              username='test',
        )
        models.UserProfile.objects.create(user=self.user)

        # create a game
        self.game = models.Game.create(self.user.profile, 1, 10)


    def test_next_flights(self):
        """Test that we can see next flights"""
        airport = self.game.airports.order_by('?')[0]
        now = datetime.datetime(2011, 11, 17, 11, 0)
        time1 = datetime.datetime(2011, 11, 17, 11, 30)
        dest1 = random.choice(airport.destinations.all())
        time2 = datetime.datetime(2911, 11, 17, 12, 0)
        dest2 = random.choice(airport.destinations.all())

        flight1 = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = dest1,
                depart_time = time1,
                flight_time = 200)

        flight2 = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = dest2,
                depart_time = time2,
                flight_time = 200)

        next_flights = airport.next_flights(self.game, now,
                future_only=True, auto_create=False)
        self.assertEqual(len(next_flights), 2)
        next_flights = airport.next_flights(self.game, time1,
                future_only=True, auto_create=False)
        self.assertEqual(len(next_flights), 1)
        next_flights = airport.next_flights(self.game, time2,
                future_only=True, auto_create=False)
        self.assertEqual(len(next_flights), 0)

    def test_distinct_airports(self):
        """Ensure games doesn't have duplicate airports"""
        for i in range(10):
            game = models.Game.create(self.user.profile, 1,
                    random.randint(10, 50))
            codes = game.airports.values_list('code', flat=True)
            self.assertEqual(len(set(codes)), len(codes))

class FlightTest(TestCase):
    """Test the Flight Model"""

    def setUp(self):
        "setup"

        # create user and game
        self.user = User.objects.create(
              username='test',
        )
        models.UserProfile.objects.create(user=self.user)

        # create a game
        self.game = models.Game.create(self.user.profile, 1, 10)

    def test_in_flight(self):
        """Test the in_flight() and cancel() methods"""
        airports = models.Airport.objects.filter(game=self.game)
        airport = random.choice(airports)
        destination = random.choice(airport.destinations.all())
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = destination,
                depart_time = depart_time,
                flight_time = flight_time)

        now = datetime.datetime(2011, 11, 18, 4, 0)
        self.assertFalse(flight.in_flight(now))

        now = datetime.datetime(2011, 11, 18, 5, 0)
        self.assertTrue(flight.in_flight(now))

        now = datetime.datetime(2011, 11, 18, 6, 1)
        self.assertFalse(flight.in_flight(now))

        # verify that in-flight flights can't be cancelled
        now = datetime.datetime(2011, 11, 18, 5, 0)
        self.assertRaises(models.Flight.AlreadyDeparted, flight.cancel, now)

        # cancel a flight and verify it's not in flight during it's usual
        # flight time
        now = datetime.datetime(2011, 11, 18, 4, 0)
        flight.cancel(now)
        now = datetime.datetime(2011, 11, 18, 5, 0)
        self.assertFalse(flight.in_flight(now))

    def test_flight_properties(self):
        """Test properties on the Flight model"""
        airports = models.Airport.objects.all()
        airport = random.choice(airports)
        destination = self.game.airports.order_by('?')[0]
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = destination,
                depart_time = depart_time,
                flight_time = flight_time)

        self.assertEqual(flight.destination_city, destination.city)
        self.assertEqual(flight.origin_city, airport.city)

    def test_next_flight_to(self):
        """Test the next_flight_to() method"""
        now = datetime.datetime(2011, 11, 17, 11, 0)
        airport = self.game.airports.order_by('?')[0]
        city_id = (self.game.airports
            .exclude(city=airport.city)
            .values_list('city', flat=True)
            .order_by('?')[0])
        city = models.City.objects.get(id=city_id)

        dest = models.Airport.objects.filter(game=self.game, city=city)[0]
        time1 = datetime.datetime(2011, 11, 17, 11, 30)
        flight1 = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = dest,
                depart_time = time1,
                flight_time = 200)

        time2 = datetime.datetime(2011, 11, 17, 12, 0)
        flight2 = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = dest,
                depart_time = time2,
                flight_time = 200)

        city_id = (self.game.airports
            .exclude(city=airport.city)
            .values_list('city', flat=True)
            .order_by('?')[0])
        city2 = models.City.objects.get(id=city_id)
        dest2 = models.Airport.objects.filter(game=self.game, city=city2)[0]
        flight3 = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = dest2,
                depart_time = time2,
                flight_time = 200)

        self.assertEqual(airport.next_flight_to(self.game, city, now), flight1)
        airport2 = models.Airport.objects.filter(city=city)[0]
        self.assertEqual(airport.next_flight_to(self.game, airport2,
            now), flight1)
        self.assertEqual(airport.next_flight_to(self.game, city2, now), flight3)

        # delay flight1
        flight1.delay(datetime.timedelta(minutes=450), now)
        self.assertEqual(airport.next_flight_to(self.game, city, now), flight2)

    def test_create_flights(self):
        """test the create flights method"""
        airports = models.Airport.objects.all()
        airport = random.choice(airports)

        self.assertEqual(models.Flight.objects.all().count(), 0)

        now = datetime.datetime(2011, 11, 20, 6, 43)
        airport.create_flights(self.game, now)
        destinations = airport.destinations.all()
        self.assertNotEqual(models.Flight.objects.all().count(), 0)

        for flight in models.Flight.objects.all():
            self.assertEqual(flight.origin, airport)
            self.assertNotEqual(flight.destination, airport)
            self.assertTrue(flight.destination in destinations)
            self.assertTrue(flight.depart_time > now)
            self.assertNotEqual(flight.flight_time, 0)

    def test_to_dict(self):
        """Test the to_dict() method"""
        airports = models.Airport.objects.all()
        airport = random.choice(airports)
        destination = random.choice(airport.destinations.all())
        now = datetime.datetime(2011, 11, 18, 4, 0)
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
                game = self.game,
                origin = airport,
                destination = destination,
                depart_time = depart_time,
                flight_time = flight_time)

        d = flight.to_dict(now)
        self.assertEqual(type(d), dict)
        self.assertEqual(sorted(d.keys()), sorted([
            'number', 'depart_time', 'arrival_time', 'destination',
            'origin', 'status']))
        self.assertEqual(d['status'], 'On time')

        flight.delay(datetime.timedelta(minutes=20),
                datetime.datetime(2011, 11, 18, 4, 0))
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Delayed')

        flight.cancel(now)
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Cancelled')

class UserProfileTest(TestCase):
    """Test the UserProfile model"""

    def setUp(self):
        """setup for UserProfileTest"""
        # create a user
        self.user = User.objects.create_user(username='test',
            email='test@test.com', password='test')
        self.up = models.UserProfile.objects.create(user=self.user)

        # create a game
        self.game = models.Game.create(self.user.profile, 3, 25)
        self.game.begin()

    def test_location_and_update(self):
        """Test the Flight.location() and Game.update() methods"""
        now = datetime.datetime(2011, 11, 20, 7, 13)
        l = self.up.location(now, self.game, self.up)
        self.assertEqual(l, (None, None))

        airport = random.choice(models.Airport.objects.all())
        airport.create_flights(self.game, now)
        flight = random.choice(airport.flights.all())

        self.up.airport = airport
        self.up.save()
        self.up.purchase_flight(flight, now)
        l = self.up.location(now, self.game, self.up)
        self.assertEqual(self.up.ticket, flight)
        self.assertEqual(l, (airport, flight))

        # Take off!, assert we are in flight
        x = self.game.update(self.up,
                flight.depart_time) # timestamp, airport, ticket
        self.assertEqual(x[1], None)
        self.assertEqual(x[2], flight)

        # when flight is delayed we are still in the air
        original_arrival = flight.arrival_time
        flight.delay(datetime.timedelta(minutes=20), now)
        x = self.game.update(self.up, original_arrival)
        self.assertEqual(x[1], None)
        self.assertEqual(x[2], flight)

        # now land
        now = flight.arrival_time + datetime.timedelta(minutes=1)
        x = self.game.update(self.up, now)
        self.assertEqual(x[1], flight.destination)
        self.assertEqual(x[2], None)

    def test_purchase_flight(self):
        """Test the purchase_flight() method"""
        now = datetime.datetime(2011, 11, 20, 7, 13)
        x = self.game.update(self.up, now)
        self.assertEqual(x[1], self.game.start_airport)
        self.assertEqual(x[2], None)

        airport = random.choice(models.Airport.objects.all())
        airport.create_flights(self.game, now)
        flight = random.choice(airport.flights.all())

        # assert we can't buy the ticket (flight) if we're not at the airport
        self.assertRaises(models.Flight.NotAtDepartingAirport,
                self.up.purchase_flight, flight, now)

        self.up.airport = airport
        self.up.save()

        # attempt to buy a flight while in flight
        self.up.purchase_flight(flight, now)
        now = flight.depart_time
        flight2 = random.choice(airport.flights.exclude(id=flight.id))
        self.assertRaises(models.Flight.AlreadyDeparted,
                self.up.purchase_flight, flight2, now)

        # ok let's land
        now = flight.arrival_time + datetime.timedelta(minutes=1)
        now, airport, flight = self.game.update(self.up, now)
        self.up.airport = airport

        # make sure we have flights
        airport.create_flights(self.game, now)

        # lounge around for a while...
        now = now + datetime.timedelta(minutes=60)

        # find a flight that's already departed
        flight3 = random.choice(airport.flights.filter(game=self.game,
            depart_time__lte=now))

        # try to buy it
        self.assertRaises(models.Flight.AlreadyDeparted,
                self.up.purchase_flight, flight3, now)

class CurrentGameTest(TestCase):
    """Test the current_game() method in UserProfile"""
    def setUp(self):
        self.users = create_users(2)

    def test_no_games_created(self):
        """Test that when there are no games created, current_game is
        None"""
        user = self.users[0]
        self.assertEqual(user.profile.current_game, None)

    def test_game_not_started(self):
        """Test that th when a Game has not yet begun, but the player is in
        the game, returns the Game"""
        user = self.users[0]
        user2 = self.users[1]

        game = models.Game.create(user.profile, 1, 10)
        self.assertEqual(user.profile.current_game, game)
        self.assertEqual(user.profile.current_game.state, game.NOT_STARTED)

        # add a user to the game, don't start it yet
        self.assertEqual(user2.profile.current_game, None)
        game.add_player(user2.profile)
        self.assertEqual(user2.profile.current_game, game)
        self.assertEqual(user2.profile.current_game.state, game.NOT_STARTED)

        game.begin()
        self.assertEqual(user.profile.current_game, game)
        self.assertEqual(user.profile.current_game.state, game.IN_PROGRESS)
        self.assertEqual(user2.profile.current_game.state, game.IN_PROGRESS)

    def test_game_over(self):
        """Test that when a game is over current_game returns the game, but
        statis us GAME_OVER"""
        user = self.users[0]
        game = models.Game.create(user.profile, 1, 10)

        game.begin()
        self.assertEqual(user.profile.current_game, game)

        # monkey
        game.is_over = lambda: True
        game.update(user)

        # game should be over
        self.assertEqual(user.profile.current_game, game)
        self.assertEqual(game.state, game.GAME_OVER)

class PerGameAirports(TestCase):
    def setUp(self):
        self.user = create_users(1)[0]

    def test_game_has_subset_of_airports(self):
        game = models.Game.create(
                host = self.user.profile,
                goals = 4,
                airports = 10,
                dest_per_airport = 2)

        self.assertEqual(game.airports.count(), 10)

class Messages(TestCase):
    """Test the messages model"""

    def setUp(self):
        self.user = create_users(1)[0]

    def test_no_messages(self):
        """Test that when user is first created there are no messages except the welcome message"""
        messages = models.Message.objects.filter(profile=self.user.profile)
        self.assertEqual(messages.count(), 1)
        self.assertTrue(messages[0].text.startswith('Welcome'))

    def test_get_latest(self):
        """Test the get_latest() method"""
        message = models.Message.send(self.user, 'Test 1')

        last_message = models.Message.get_latest(self.user)
        self.assertEqual(last_message, message)

        message = models.Message.send(self.user, 'Test 2')
        last_message = models.Message.get_latest(self.user)
        self.assertEqual(last_message, message)

    def test_in_view(self):
        """Test in a view"""
        # we use the games_info view so we dont have to create any games
        view = reverse('games_info')

        self.client.login(username='user1', password='test')

        # inject a message
        message = models.Message.send(self.user, 'Test 1')
        response = json.loads(self.client.get(view).content)
        self.assertEqual(response['message_id'], message.id)

        # and again
        response = json.loads(self.client.get(view).content)
        self.assertEqual(response['message_id'], message.id)

        # insert 2 messages
        models.Message.send(self.user, 'Test 2')
        message = models.Message.send(self.user, 'Test 3')
        response = json.loads(self.client.get(view).content)
        self.assertEqual(response['message_id'], message.id)


    def test_messages_view(self):
        """Test the messages() view"""
        view = reverse('messages')

        messages = []
        for i in range(6):
            messages.append(models.Message.send(self.user, 'Test %s' % i))

        self.client.login(username='user1', password='test')
        response = self.client.get(view)
        for message in messages:
            self.assertContains(response, 'data-id="%s"' % message.id)

