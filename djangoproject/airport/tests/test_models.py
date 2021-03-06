import datetime
import json
import random
import time
from unittest.mock import call, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.test import TestCase, TransactionTestCase

from airport import lib, models
from airport.conf import settings
from airport.tests import BaseTestCase


class AirportMasterTest(BaseTestCase):
    """Tests for the AirportMaster model"""

    def test_str(self):
        """str()"""
        # Given the master airport
        airport = models.AirportMaster.objects.get(code='MIA')

        # When we call str() on it
        result = str(airport)

        # Then we get the expected result
        self.assertEqual(result, 'Master Airport: Miami International')


class AirportTest(BaseTestCase):

    """Test the Airport model."""

    def test_get_destinations(self):
        # test the "get_destinations()" method
        airport = self.game.airports.all()[0]
        destinations = airport.get_destinations(5)
        destinations = list(destinations)

        self.assertTrue(len(destinations) <= 5)
        self.assertTrue(airport not in destinations)
        self.assertTrue(airport.city not in [i.city for i in destinations])

    def test_str(self):
        """str()"""
        # Given the airport
        # Note we have to do it this complex way because we want to ensure that
        # the "random" airport we pick is not already used in the game or the
        # airport's city already used
        used_cities = models.Airport.objects.filter(game=self.game)
        used_cities = used_cities.values_list('master__city', flat=True)

        available_airports = models.AirportMaster.objects.exclude(city__in=used_cities)

        airport_master = available_airports[0]
        airport = models.Airport.objects.create(game=self.game, master=airport_master)

        # Then when we call str() on it
        result = str(airport)

        # Then we get the expected result
        self.assertEqual(result, airport.city.name)

    def test_str_airports_per_city(self):
        # Given the airports within a city with more than one airport
        jfk_master = models.AirportMaster.objects.get(code='JFK')
        jfk = models.Airport.objects.create(game=self.game, master=jfk_master)
        lga_master = models.AirportMaster.objects.get(code='LGA')
        lga = models.Airport.objects.create(game=self.game, master=lga_master)

        # Then when we call str() on them
        str_jfk = str(jfk)
        str_lga = str(lga)

        # Then we get the expected result
        self.assertEqual(str_jfk, 'New York City JFK')
        self.assertEqual(str_lga, 'New York City LGA')

    def test_cannot_have_self_as_destination(self):
        # Given the airports within a city with more than one airport
        jfk_master = models.AirportMaster.objects.get(code='JFK')
        jfk = models.Airport.objects.create(game=self.game, master=jfk_master)
        lga_master = models.AirportMaster.objects.get(code='LGA')
        lga = models.Airport.objects.create(game=self.game, master=lga_master)

        # When we make one a destination of the other
        # Then we get a ValidationError
        with self.assertRaises(ValidationError):
            lga.destinations.add(jfk)
            lga.save()

    def test_next_flights(self):
        # grab a random airport, but exclude the game's starting airport
        # because game.begin() would have already populated it with flights
        airports = self.game.airports.exclude(pk=self.game.start_airport.pk)
        airport = models.random_choice(airports)
        now = datetime.datetime(2011, 11, 17, 11, 0)
        time1 = datetime.datetime(2011, 11, 17, 11, 30)
        dest1 = random.choice(airport.destinations.all())
        time2 = datetime.datetime(2911, 11, 17, 12, 0)
        dest2 = random.choice(airport.destinations.all())

        # flight 1
        models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=dest1,
            depart_time=time1,
            flight_time=200,
        )

        # flight 2
        models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=dest2,
            depart_time=time2,
            flight_time=200,
        )

        next_flights = airport.next_flights(now, future_only=True, auto_create=False)
        self.assertEqual(len(next_flights), 2)
        next_flights = airport.next_flights(time1, future_only=True, auto_create=False)
        self.assertEqual(len(next_flights), 1)
        next_flights = airport.next_flights(time2, future_only=True, auto_create=False)
        self.assertEqual(len(next_flights), 0)

    def test_next_flight_to(self):
        # given the origin
        origin = self.game.start_airport

        # and a destination
        dest = origin.destinations.distinct()[0]
        city = dest.city

        # when we create 2 flights to the destination at different times
        now = datetime.datetime.fromtimestamp(0)
        flt1 = models.Flight.objects.create(
            game=self.game,
            origin=origin,
            destination=dest,
            depart_time=now + datetime.timedelta(hours=1),
            flight_time=120,
            arrival_time=now + datetime.timedelta(hours=3),
        )

        # second flight starts an hour past the first
        flt2 = models.Flight.objects.create(
            game=self.game,
            origin=origin,
            destination=dest,
            depart_time=now + datetime.timedelta(hours=2),
            flight_time=120,
            arrival_time=now + datetime.timedelta(hours=4),
        )

        # when we call next_flight_to() the city
        result = origin.next_flight_to(city, now)

        # then we get the first flight
        self.assertEqual(result, flt1)

        # and if we delay that flight 90 mins
        flt1.delay(datetime.timedelta(minutes=90), now)

        # when we call next_flight_to() the city
        result = origin.next_flight_to(city, now)

        # then we get the second flight
        self.assertEqual(result, flt2)

    def test_create_flights(self):
        airports = models.Airport.objects.filter(game=self.game)
        airport = random.choice(airports.exclude(id=self.game.start_airport.id))
        destinations = airport.destinations.all()

        # we should only have the initial flights that were created at the
        # start point when the game was created
        flights = models.Flight.objects.filter(game=self.game)
        flights = flights.exclude(origin=self.game.start_airport)
        self.assertEqual(flights.count(), 0)

        now = datetime.datetime(2011, 11, 20, 6, 43)
        outgoing = models.Flight.objects.filter(game=self.game, origin=airport)
        self.assertEqual(outgoing.count(), 0)
        airport.create_flights(now)
        outgoing = models.Flight.objects.filter(game=self.game, origin=airport)
        self.assertNotEqual(outgoing.count(), 0)

        for flight in outgoing:
            self.assertEqual(flight.origin, airport)
            self.assertNotEqual(flight.destination, airport)
            self.assertTrue(flight.destination in destinations)
            self.assertTrue(flight.depart_time > now)
            self.assertNotEqual(flight.flight_time, 0)

    @patch('airport.models.random_time')
    def test_create_flights_cushion(self, mock_random_time):
        # given the airport
        airport = self.game.start_airport

        # and a flight that departs at 9:50
        destination = airport.destinations.all()[0]
        depart_time = datetime.datetime(year=2015, month=3, day=12, hour=9, minute=50)
        models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=destination,
            number=666,
            depart_time=depart_time,
            arrival_time=depart_time + datetime.timedelta(minutes=120),
            flight_time=120,
        )

        # when the time is 9:45 (i.e. the flight has departed)
        now = depart_time + datetime.timedelta(minutes=5)

        # when when we call create_flights
        # you'll see why i'm mocking this later
        mock_random_time.return_value = depart_time + datetime.timedelta(minutes=30)
        flights = airport.create_flights(now)

        # then the next flight to the destination will not depart before 10:10
        # (20 minute cushion)
        # If we didn't mock random_time and just check for the depart_time then
        # most of the time this test would pass.  So instead we mock it and
        # assert that it was called with the expected starting time
        flight = [i for i in flights if i.destination == destination][0]
        start_time = depart_time + datetime.timedelta(minutes=20)
        expected_call = call(start_time, 59)

        self.assertTrue(expected_call in mock_random_time.mock_calls)
        msg = 'The next flight was created < 20 mins from the previous'
        self.assertTrue(flight.depart_time >= start_time, msg)


class GameManagerTest(TransactionTestCase):
    def test_create_game_no_duplicate_airports(self):
        """Ensure games doesn't have duplicate airports"""
        for i in range(10):
            user = User.objects.create_user(
                username='user%s' % i, email='user%s@test.com' % i, password='test'
            )
            game = models.Game.objects.create_game(
                host=user.player, goals=1, airports=random.randint(10, 50)
            )
            codes = game.airports.values_list('master__code', flat=True)
            self.assertEqual(len(set(codes)), len(codes))

    def test_game_has_subset_of_airports(self):
        player = BaseTestCase.create_players(1)[0]

        game = models.Game.objects.create_game(
            host=player, goals=4, airports=10, density=2
        )

        self.assertEqual(game.airports.count(), 10)


class GamePause(BaseTestCase):
    """Test the pausing/resuming of a game"""

    def setUp(self):
        self.players = self.create_players(2)

    def test_begin_not_paused(self):
        """Test that when you begin a game it is not paused"""
        game = models.Game.objects.create_game(self.players[0], 1, 10)
        game.begin()

        self.assertNotEqual(game.state, game.PAUSED)

    def test_pause_method(self):
        """Test the pause method"""
        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()
        game.pause()

        self.assertEqual(game.state, game.PAUSED)

    def test_game_time_doesnt_change(self):
        """Test that the game time doesn't change when paused"""
        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()
        game.pause()
        orig_time = game.time
        time.sleep(1)
        new_time = game.time
        self.assertEqual(orig_time, new_time)

    def test_info_view(self):
        """Test the info view of a paused game"""
        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()
        game.pause()

        self.client.login(username=self.players[0].username, password='test')
        response = self.client.get(reverse('info'))
        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response['game_state'], 'Paused')

    def test_ticket_purchase(self):
        """Ensure you can't purchase tickets on a paused game"""
        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()
        game.pause()

        airport = game.start_airport
        flights = airport.next_flights(game.time, future_only=True)
        flight = flights[0]

        self.assertRaises(
            game.Paused, self.players[0].purchase_flight, flight, game.time
        )

    @patch('airport.lib.send_message')
    def test_in_flight(self, send_message):
        """Test that you are paused in-flight"""

        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()

        airport = game.start_airport
        flights = airport.next_flights(game.time, future_only=True)
        flights.sort(key=lambda x: x.depart_time)
        flight = flights[0]

        now1 = lib.take_turn(game, flight.depart_time)
        self.assertTrue(flight.in_flight(now1))

        game.pause()
        now2 = lib.take_turn(game, now1)
        self.assertTrue(flight.in_flight(now2))
        self.assertEqual(now1, now2)

    def test_game_join(self):
        """Assure that you can still join a game while paused"""
        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()
        game.pause()

        game.add_player(self.players[1])
        self.assertEqual(
            set(game.players.filter(ai_player=False)),
            set([self.players[0], self.players[1]]),
        )

    def test_active_game_status(self):
        """Assert that the game status shows the game as paused"""
        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()
        game.pause()

        user2 = self.players[1]
        self.client.login(username=user2.username, password='test')
        response = self.client.get(reverse('games_info'))
        response = json.loads(response.content.decode('utf-8'))
        response_game = list(filter(lambda x: x['id'] == game.id, response['games']))[0]

        self.assertEqual(response_game['status'], 'Paused')

    def test_resume(self):
        """Assert that resume works and the time doesn't fast-forward"""
        game = models.Game.objects.create_game(
            host=self.players[0], goals=1, airports=10
        )
        game.begin()
        game.pause()

        orig_time = game.time
        time.sleep(3)
        game.resume()
        new_time = game.time
        time_difference_secs = (new_time - orig_time).total_seconds()
        self.assertTrue(time_difference_secs < game.TIMEFACTOR)


class CreateGameTest(BaseTestCase):
    """Tests for the create_game() method"""

    def test_with_start_airport(self):
        self.game.end()

        # given the start airport
        masters = models.AirportMaster.objects.all()
        start_airport = models.random_choice(masters)

        # When we call create_airport telling it to start there
        game = models.Game.objects.create_game(
            self.player, 1, 10, ai_player=False, start=start_airport
        )

        # Then it starts there
        self.assertEqual(game.start_airport.code, start_airport.code)

    @patch('airport.views.lib.send_message')
    def test_with_view(self, mock_send_message):
        self.game.end()

        # given the url to create a game
        url = reverse('airport.views.games_create')

        # the originating city
        start = models.City.objects.get(name='Raleigh')
        start_lat = start.latitude
        start_lon = start.longitude

        # And relevant POST data
        post = {
            'goals': 1,
            'airports': 10,
            'ai_player': 'No',
            'start_lat': start_lat,
            'start_lon': start_lon,
        }

        # when we create a game through the view
        self.client.login(username='user1', password='test')
        response = self.client.post(url, post)

        # Then we're given a game starting at the requested airport
        response = json.loads(response.content.decode('utf-8'))
        game_id = response['current_game']
        game = models.Game.objects.get(pk=game_id)
        self.assertEqual(game.start_airport.city, start)

    @patch('airport.views.lib.send_message')
    def test_with_view_with_bogus_city(self, mock_send_message):
        self.game.end()

        # given the url to create a game
        url = reverse('airport.views.games_create')

        # the originating with we dont' have
        start = 'Bogus City'

        # And relevant POST data
        post = {
            'goals': 1,
            'airports': 10,
            'ai_player': 'No',
            'start_city': start,
        }

        # when we create a game through the view
        self.client.login(username='user1', password='test')
        response = self.client.post(url, post)

        # Then we're still given a game, but not at the airport (obviously)
        response = json.loads(response.content.decode('utf-8'))
        game_id = response['current_game']
        game = models.Game.objects.get(pk=game_id)
        self.assertNotEqual(game.start_airport.city.name, start)


class FlightTest(BaseTestCase):
    def test_in_flight(self):
        """Test the in_flight() and cancel() methods"""
        airports = models.Airport.objects.filter(game=self.game)
        airport = random.choice(airports)
        destination = random.choice(airport.destinations.all())
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=destination,
            depart_time=depart_time,
            flight_time=flight_time,
        )

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

    def test_cancelled_has_landed(self):
        # Given flight
        airport = models.Airport.objects.filter(game=self.game)[0]
        now = self.game.time
        flight = airport.next_flights(now)[0]

        # When we cancel it
        flight.cancel(now)

        # Then it is has not landed
        self.assertFalse(flight.has_landed(now))

    def test_cancel_with_ticketed_passenger(self):
        # Given flight
        airport = self.game.start_airport
        now = self.game.time
        flight = airport.next_flights(now, True)[0]

        # And the player that's on that flight
        self.player.purchase_flight(flight, now)
        self.assertNotEqual(self.player.ticket, None)

        # When the flight gets cancelled
        flight.cancel(self.game.time)

        # Then the player's ticket is revoked
        # (we need to re-fetch the player)
        player = models.Player.objects.get(pk=self.player.pk)
        self.assertEqual(player.ticket, None)

    def test_delay(self):
        # Given the flight
        airport = self.game.start_airport
        now = self.game.time
        flight = airport.next_flights(now, True)[0]

        # When we delay the flight
        orig_depart_time = flight.depart_time
        delay = datetime.timedelta(minutes=30)
        flight.delay(delay, now)

        # Then the flight is delayed
        self.assertEqual(flight.state, 'Delayed')
        self.assertEqual(flight.depart_time, orig_depart_time + delay)

    def test_delay_cancelled_flight(self):
        # Given the cancelled flight
        airport = self.game.start_airport
        now = self.game.time
        flight = airport.next_flights(now, True)[0]
        flight.cancel(now)

        # When we try to delay it
        # Then it raises the Finished exception
        with self.assertRaises(flight.Finished):
            delay = datetime.timedelta(minutes=30)
            flight.delay(delay)

    def test_delay_departed_flight(self):
        """delay() departed flight"""
        # Given the depareted flight
        airport = self.game.start_airport
        now = self.game.time
        flight = airport.next_flights(now)[0]
        if flight.depart_time > now:  # ensure we're departed
            flight.depart_time = now
            flight.save()

        # When we try to delay it
        # Then it raises the AlreadyDeparted exception
        with self.assertRaises(flight.AlreadyDeparted):
            delay = datetime.timedelta(minutes=30)
            flight.delay(delay)

    def test_to_dict(self):
        """Test the to_dict() method"""
        airports = models.Airport.objects.filter(game=self.game)
        airport = random.choice(airports)
        destination = random.choice(airport.destinations.all())
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=destination,
            depart_time=depart_time,
            flight_time=flight_time,
        )

        now = datetime.datetime(2011, 11, 18, 4, 0)

        d = flight.to_dict(now)
        self.assertEqual(type(d), dict)
        self.assertEqual(
            sorted(d.keys()),
            sorted(
                [
                    'number',
                    'depart_time',
                    'arrival_time',
                    'destination',
                    'id',
                    'origin',
                    'status',
                ]
            ),
        )
        self.assertEqual(d['status'], 'On Time')

        now = datetime.datetime(2011, 11, 18, 4, 45)
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Boarding')

        flight.delay(
            datetime.timedelta(minutes=20), datetime.datetime(2011, 11, 18, 4, 0)
        )
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Delayed')

        flight.cancel(now)
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Cancelled')

    def test_flight_time_constant(self):
        """Test that the connection time between two airports is always
        constant (ignoring cancellations/delays and the like"""

        now = self.game.time
        for source in self.game.airports.all():
            for flight in source.next_flights(now):
                destination = flight.destination
                s2d = flight.flight_time
                d2s = [
                    i for i in destination.next_flights(now) if i.destination == source
                ][0].flight_time
                # We use assertAlmostEqual to compensate for rounding (integer
                # division)
                self.assertAlmostEqual(s2d, d2s, delta=1)

    def test_get_flight_number(self):
        # given the flight created without a number
        flight = models.Flight(
            game=self.game,
            origin=self.game.start_airport,
            destination=self.game.start_airport.destinations.all()[0],
            depart_time=self.game.time,
        )

        # when we call .get_flight_number()
        number = flight.get_flight_number()

        # then the flight gets a number
        self.assertNotEqual(flight.number, None)
        self.assertEqual(flight.number, number)

    def test_get_flight_number_already_has_number(self):
        # given the flight that already has a number
        airport = self.game.start_airport
        flights = airport.create_flights(self.game.time)
        flight = flights[0]
        orig_number = flight.number
        assert orig_number

        # when we call .get_flight_number()
        result = flight.get_flight_number()

        # then nothing changes because that flight already had a number
        self.assertEqual(flight.number, orig_number)
        self.assertEqual(result, orig_number)


class PlayerTest(BaseTestCase):
    """Test the Player model"""

    def setUp(self):
        self.players = self.create_players(2)
        self.player = self.players[0]
        self.game = self.create_game(self.players[0])

    @patch('airport.lib.send_message')
    def test_location_and_update(self, send_message):
        """Test the Flight.location() and take_turn()"""
        self.game.begin()
        now = self.game.time
        l = self.player.location(now)
        self.assertEqual(l, (self.game.start_airport, None))

        airport = self.game.start_airport
        airport.create_flights(now)
        flight = random.choice(airport.flights.all())

        self.player.airport = airport
        self.player.save()
        lib.take_turn(self.game, now)
        self.player.purchase_flight(flight, self.game.time)
        l = self.player.location(now)
        self.assertEqual(self.player.ticket, flight)
        self.assertEqual(l, (airport, flight))

        # Take off!, assert we are in flight
        lib.take_turn(self.game, flight.depart_time, throw_wrench=False)
        # re-fetch player
        player = models.Player.objects.get(pk=self.player.pk)
        self.assertEqual(player.airport, None)
        self.assertEqual(player.ticket, flight)

        # when flight is delayed we are still in the air
        original_arrival = flight.arrival_time
        flight.delay(datetime.timedelta(minutes=20), now)
        lib.take_turn(self.game, original_arrival)
        player = models.Player.objects.get(pk=self.player.pk)
        self.assertEqual(player.airport, None)
        self.assertEqual(player.ticket, flight)

        # now land
        now = flight.arrival_time + datetime.timedelta(minutes=1)
        lib.take_turn(self.game, now)
        player = models.Player.objects.get(pk=self.player.pk)
        self.assertEqual(player.airport, flight.destination)
        self.assertEqual(player.ticket, None)

    @patch('airport.lib.send_message')
    def test_purchase_flight(self, send_message):
        player = self.player
        now = datetime.datetime(2011, 11, 20, 7, 13)
        lib.take_turn(self.game, now)
        self.assertEqual(player.airport, self.game.start_airport)
        self.assertEqual(player.ticket, None)

        airport = random.choice(models.Airport.objects.exclude(pk=player.airport.pk))
        airport.create_flights(now)
        flight = random.choice(airport.flights.all())

        # assert we can't buy the ticket (flight) if we're not at the airport
        self.assertRaises(
            models.Flight.NotAtDepartingAirport, player.purchase_flight, flight, now
        )

        player.airport = airport
        player.save()

        # attempt to buy a flight while in flight
        player.purchase_flight(flight, now)
        now = flight.depart_time
        next_flights = airport.next_flights(now, future_only=True, auto_create=True)
        flight2 = random.choice(next_flights)
        self.assertRaises(
            models.Flight.AlreadyDeparted, player.purchase_flight, flight2, now
        )

        # ok let's land
        now = flight.arrival_time + datetime.timedelta(minutes=1)
        now = lib.take_turn(self.game, now)

        # make sure we have flights
        airport.create_flights(now)

        # lounge around for a while...
        now = now + datetime.timedelta(minutes=60)

        # find a flight that's already departed
        flight3 = random.choice(
            airport.flights.filter(game=self.game, depart_time__lte=now)
        )

        # try to buy it
        self.assertRaises(
            models.Flight.AlreadyDeparted, player.purchase_flight, flight3, now
        )

    def test_current_game_no_games_created(self):
        player = self.players[1]
        self.assertEqual(player.current_game, None)

    def test_current_game_game_not_started(self):
        self.game.end()
        player = self.players[0]
        player2 = self.players[1]

        game = models.Game.objects.create_game(host=player, goals=1, airports=10)
        self.assertEqual(player.current_game, game)
        self.assertEqual(player.current_game.state, game.NOT_STARTED)

        # add a user to the game, don't start it yet
        self.assertEqual(player2.current_game, None)
        game.add_player(player2)
        self.assertEqual(player2.current_game, game)
        self.assertEqual(player2.current_game.state, game.NOT_STARTED)

        game.begin()
        self.assertEqual(player.current_game, game)
        self.assertEqual(player.current_game.state, game.IN_PROGRESS)
        self.assertEqual(player2.current_game.state, game.IN_PROGRESS)

    @patch('airport.lib.send_message')
    def test_current_game_game_over(self, send_message):
        self.game.end()
        player = self.players[0]
        game = models.Game.objects.create_game(host=player, goals=1, airports=10)

        game.begin()
        self.assertEqual(player.current_game, game)

        game.end()
        lib.take_turn(game)

        # game should be over
        self.assertEqual(player.current_game, game)
        self.assertEqual(game.state, game.GAME_OVER)


class AIPlayerTest(BaseTestCase):
    def test_ai_player_optional(self):
        """AI Player is optional"""
        self.game.end()
        game = models.Game.objects.create_game(
            ai_player=True, host=self.player, goals=1, airports=10
        )

        ai_player = game.players.filter(ai_player=True)
        self.assertTrue(ai_player.exists())
        game.end()

        game = models.Game.objects.create_game(
            ai_player=False, host=self.player, goals=1, airports=10
        )

        ai_player = game.players.filter(ai_player=True)
        self.assertFalse(ai_player.exists())

    @patch('airport.lib.send_message')
    def test_view(self, send_message):
        url = reverse('airport.views.games_create')
        self.game.end()

        self.client.login(username='user1', password='test')

        # first try with an ai player
        form = {'goals': 1, 'airports': 20, 'ai_player': 'Yes'}

        self.client.post(url, form)
        self.assertTrue(send_message.called)

        args = send_message.call_args[0]
        self.assertEqual(args[0], 'game_created')
        game_id = args[1]
        game = models.Game.objects.get(pk=game_id)
        ai_player = game.players.filter(ai_player=True)
        self.assertTrue(ai_player.exists())
        game.end()

        # now try with out an ai player
        form = {'goals': 1, 'airports': 20, 'ai_player': 'No'}

        self.client.post(url, form)

        args = send_message.call_args[0]
        self.assertEqual(args[0], 'game_created')
        game_id = args[1]
        game = models.Game.objects.get(pk=game_id)
        ai_player = game.players.filter(ai_player=True)
        self.assertFalse(ai_player.exists())

    @patch('airport.lib.send_message')
    def test_cannot_buy_full_flight(self, send_message):
        """An AI player cannot attempt to buy a full flight."""
        self.game.end()
        # given the game with ai player
        game = models.Game.objects.create_game(
            ai_player=True, host=self.player, goals=1, airports=10
        )
        ai_player = game.players.get(ai_player=True)

        # When only one flight is outbound
        game.begin()
        airport = game.start_airport
        now = lib.take_turn(game)
        flights_out = airport.next_flights(now, future_only=True, auto_create=False)
        for flight in flights_out[:-1]:
            flight.cancel(now)
        last_flight = flights_out[-1]

        # but it's full
        last_flight.full = True
        last_flight.save()

        # and the ai_player makes a move
        ai_player.make_move(game, now)

        # it doesn't try to buy a full flight (it will raise an exception if it
        # does)
        self.assertEqual(ai_player.ticket, None)


class Messages(BaseTestCase):
    """Test the messages model"""

    def setUp(self):
        self.player = self.create_players(1)[0]

    def test_no_messages(self):
        # Test that when user is first created there are no messages except the
        # welcome message"""
        messages = models.Message.objects.filter(player=self.player)
        self.assertEqual(messages.count(), 1)
        self.assertTrue(messages[0].text.startswith('Welcome'))

    def test_get_latest(self):
        """Test the get_latest() method"""
        message = models.Message.objects.send(self.player, 'Test 1')

        last_message = models.Message.objects.get_latest(self.player)
        self.assertEqual(last_message, message)

        message = models.Message.objects.send(self.player, 'Test 2')
        last_message = models.Message.objects.get_latest(self.player)
        self.assertEqual(last_message, message)

    def test_in_view(self):
        """Test in a view"""
        view = reverse('messages')

        self.client.login(username='user1', password='test')

        # inject a message
        message = models.Message.objects.send(self.player, 'Test 1')
        response = self.client.get(view)
        self.assertContains(response, 'data-id="%s"' % message.id)

        # Messages all read.. subsequent calls should return 304
        response = self.client.get(view)
        self.assertEqual(response.status_code, 304)

        # insert 2 messages
        message1 = models.Message.objects.send(self.player, 'Test 2')
        message2 = models.Message.objects.send(self.player, 'Test 3')
        response = self.client.get(view)
        self.assertContains(response, 'data-id="%s"' % message1.id)
        self.assertContains(response, 'data-id="%s"' % message2.id)

    def test_messages_view(self):
        """Test the messages() view"""
        view = reverse('messages')

        messages = []
        for i in range(6):
            messages.append(models.Message.objects.send(self.player, 'Test %s' % i))

        self.client.login(username='user1', password='test')
        response = self.client.get(view)
        for message in messages:
            self.assertContains(response, 'data-id="%s"' % message.id)

    def test_finished(self):
        """Test that when finished=False, finishers don't get a message,
        but when finished=True they do"""

        # first, we need a player to finish a game
        player = self.player
        game = models.Game.objects.create_game(
            host=player, goals=1, airports=4, density=1
        )
        game.begin()
        goal = models.Goal.objects.get(game=game)
        models.Message.objects.broadcast('this is test1', finishers=False)
        messages = models.Message.objects.get_messages(player, read=False)
        self.assertEqual(messages[0].text, 'this is test1')

        # finish
        my_achievement = models.Achievement.objects.get(
            game=game, player=player, goal=goal
        )
        my_achievement.timestamp = game.time
        my_achievement.save()

        # send a broadcast with finishers=False
        models.Message.objects.broadcast('this is test2', game, finishers=False)
        messages = models.Message.objects.get_messages(player, read=False)
        self.assertNotEqual(messages[0].text, 'this is test2')

        # send a broadcast with finishers=True
        models.Message.objects.broadcast('this is test3', game, finishers=True)
        messages = models.Message.objects.get_messages(player, read=False)
        self.assertEqual(messages[0].text, 'this is test3')


class Cities(BaseTestCase):
    """Test the Cities module"""

    def test_images(self):
        """Test that all cities have images"""
        for city in models.City.objects.all():
            self.assertNotEqual(city.image, None)

    def test_str(self):
        """str()"""
        # Given the City
        city = models.City.objects.all()[0]

        # When we call str() on it
        result = str(city)

        # Then we get the city name
        self.assertEqual(result, city.name)

    def test_get_flight_time(self):
        """get_flight_time()"""
        # Given the 2 cities
        dallas = models.City.objects.get(name='Dallas')
        raleigh = models.City.objects.get(name='Raleigh')

        # And the speed
        speed = 1  # i'm lazy

        # Then when we calculate get_flight_time()
        result = models.City.get_flight_time(dallas, raleigh, speed)

        # Then we get the time (in minutes) it takes to fligh from the two
        # cities
        self.assertEqual(result, dallas.distance_from(raleigh))

    def test_get_flight_time_with_airports(self):
        # Given the 2 airports
        dfw = models.AirportMaster.objects.get(code='DFW')
        rdu = models.AirportMaster.objects.get(code='RDU')

        # And the speed
        speed = 28

        # Then when we calculate get_flight_time()
        result = models.City.get_flight_time(dfw, rdu, speed)

        # Then we get the time (in minutes) it takes to fligh from the two
        # cities
        expected = models.City.get_flight_time(
            models.City.objects.get(name='Dallas'),
            models.City.objects.get(name='Raleigh'),
            speed,
        )
        self.assertEqual(result, expected)

    def test_airports(self):
        # given the city
        city = models.City.objects.get(name='Dallas')

        # when we call .airports()
        airports = city.airports()

        # then we get the airports for that city
        self.assertEqual(
            set(airports),
            {
                models.AirportMaster.objects.get(code='DFW'),
                models.AirportMaster.objects.get(code='DAL'),
            },
        )

    def test_distance_from_coordinates(self):
        # given the city
        city = models.City.objects.get(name='Dallas')

        # and the coordinates
        coordinates = (35.780556, -78.638889)  # Raleigh

        # when we call .distance_from_coordinates()
        distance = city.distance_from_coordinates(coordinates)

        # Then we get the expected value
        self.assertAlmostEqual(distance, 1699, delta=15)
        # according to Wolfram|Alpha

    def test_distance_from(self):
        # given the 2 cities
        city1 = models.City.objects.get(name='Dallas')
        city2 = models.City.objects.get(name='Raleigh')

        # when we calculate the distance from them
        distance = city1.distance_from(city2)

        # Then we get the expected value
        self.assertAlmostEqual(distance, 1699, delta=15)
        # according to Wolfram|Alpha

    def test_closest_to(self):
        # given the coordinates
        coords = (38.806389, -75.59)

        # when we call City.closest_to() on it
        city = models.City.closest_to(coords)

        # Then we get the expected result
        self.assertEqual(city.name, 'Baltimore')


class GoalTest(AirportTest):
    def test_stars(self):
        self.game.end()

        # given the game with 3 goals
        game = models.Game.objects.create_game(self.player, 3, 15)

        # and the last goal for that game
        goal = models.Goal.objects.filter(game=game).order_by('-order')[0]

        # when we call goal.stars()
        stars = goal.stars()

        # then we get 3 cold stars
        gold_star = settings.EXTERNALS['gold_star']
        self.assertEqual(stars.count(gold_star), 3)


class ChoiceTest(TestCase):
    def test_empty(self):
        # given the empty queryset
        queryset = models.Goal.objects.none()

        # when we call choice() on the queryset
        result = models.random_choice(queryset)

        # then we get None
        self.assertEqual(result, None)

    def test_single_item(self):
        # given the queryset with a single item
        user = User.objects.create_user(username='testtest', password='***')
        queryset = User.objects.filter(username='testtest')

        # when we call choice() on the queryset
        result = models.random_choice(queryset)

        # then we get the single entry
        self.assertEqual(result, user)

    def test_multiple_items(self):
        # given the queryset with multiple items
        for i in range(10):
            User.objects.create_user(username='test%s' % i, password='***')
        queryset = User.objects.all()

        # when we call choice() on the queryset
        result = models.random_choice(queryset)

        # then we get an entry in the queryset
        self.assertTrue(result in queryset)

    def test_item_not_in_queryset(self):
        # given the queryset with an item filtered out
        User.objects.create_user(username='excluded', password='***')
        other = User.objects.create_user(username='other', password='***')
        queryset = User.objects.exclude(username='excluded')

        # when we call choice() on the queryset
        result = models.random_choice(queryset)

        # then we don't get the excluded item
        self.assertEqual(result, other)
