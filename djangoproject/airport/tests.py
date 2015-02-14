# XXX: These tests are totally disorganized.  Need to fix
import datetime
import json
import random
import time

from django.contrib.auth.models import User
from django.core import management
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.test import TestCase, TransactionTestCase
from mock import patch

from airport import lib, models, monkeywrench


class AirportTestBase(TestCase):
    """Base class for airport tests"""

    def setUp(self):
        "setup"

        # create user and game
        self.player = self._create_players(1)[0]

        # create a game
        self.game = self._create_game(host=self.player)

    def _create_players(self, num_players):
        """create num_players  users and Players, return a tuple of the
        players created"""
        players = []
        for i in range(1, num_players + 1):
            user = User.objects.create_user(
                username='user%s' % i,
                email='user%s@test.com' % i,
                password='test'
            )
            player = models.Player()
            player.user = user
            player.save()
            players.append(player)
        return tuple(players)

    def _create_game(self, host, goals=1, airports=10):
        return models.Game.objects.create_game(
            host=host,
            goals=goals,
            airports=airports)


class AirportMasterTest(AirportTestBase):
    """Tests for the AirportMaster model"""
    def test_str(self):
        """str()"""
        # Given the master airport
        airport = models.AirportMaster.objects.get(code='MIA')

        # When we call str() on it
        result = str(airport)

        # Then we get the expected result
        self.assertEqual(result, 'Master Airport: Miami International')


class AirportTest(AirportTestBase):

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
        used_cities = used_cities.values_list('city', flat=True)

        available_airports = models.AirportMaster.objects.exclude(
            city__in=used_cities)

        airport_master = available_airports[0]
        airport = models.Airport.copy_from_master(self.game, airport_master)

        # Then when we call str() on it
        result = str(airport)

        # Then we get the expected result
        self.assertEqual(result, airport.city.name)

    def test_str_airports_per_city(self):
        # Given the airports within a city with more than one airport
        jfk_master = models.AirportMaster.objects.get(code='JFK')
        jfk = models.Airport.copy_from_master(self.game, jfk_master)
        lga_master = models.AirportMaster.objects.get(code='LGA')
        lga = models.Airport.copy_from_master(self.game, lga_master)

        # Then when we call str() on them
        str_jfk = str(jfk)
        str_lga = str(lga)

        # Then we get the expected result
        self.assertEqual(str_jfk, 'New York City JFK')
        self.assertEqual(str_lga, 'New York City LGA')

    def test_cannot_have_self_as_destination(self):
        # Given the airports within a city with more than one airport
        jfk_master = models.AirportMaster.objects.get(code='JFK')
        jfk = models.Airport.copy_from_master(self.game, jfk_master)
        lga_master = models.AirportMaster.objects.get(code='LGA')
        lga = models.Airport.copy_from_master(self.game, lga_master)

        # When we make one a destination of the other
        # Then we get a ValidationError
        with self.assertRaises(ValidationError):
            lga.destinations.add(jfk)
            lga.save()


class NextFlights(AirportTestBase):
    def runTest(self):
        """Test that we can see next flights"""
        # grab a random airport, but exclude the game's starting airport
        # because game.begin() would have already populated it with flights
        airport = self.game.airports.exclude(pk=self.game.start_airport.pk)
        airport = airport.order_by('?')[0]
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
            flight_time=200)

        # flight 2
        models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=dest2,
            depart_time=time2,
            flight_time=200)

        next_flights = airport.next_flights(now, future_only=True,
                                            auto_create=False)
        self.assertEqual(len(next_flights), 2)
        next_flights = airport.next_flights(time1, future_only=True,
                                            auto_create=False)
        self.assertEqual(len(next_flights), 1)
        next_flights = airport.next_flights(time2, future_only=True,
                                            auto_create=False)
        self.assertEqual(len(next_flights), 0)


class DistinctAirports(TransactionTestCase):
    def runTest(self):
        """Ensure games doesn't have duplicate airports"""
        for i in range(10):
            user = User.objects.create_user(
                username='user%s' % i,
                email='user%s@test.com' % i,
                password='test'
            )
            game = models.Game.objects.create_game(
                host=user.player,
                goals=1,
                airports=random.randint(10, 50)
            )
            codes = game.airports.values_list('code', flat=True)
            self.assertEqual(len(set(codes)), len(codes))


class FlightTest(AirportTestBase):
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
            flight_time=flight_time)

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


class NextFlightTo(AirportTestBase):
    def runTest(self):
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
            game=self.game,
            origin=airport,
            destination=dest,
            depart_time=time1,
            flight_time=200)

        time2 = datetime.datetime(2011, 11, 17, 12, 0)
        flight2 = models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=dest,
            depart_time=time2,
            flight_time=200)

        city_id = (self.game.airports
                   .exclude(city=airport.city)
                   .values_list('city', flat=True)
                   .order_by('?')[0])
        city2 = models.City.objects.get(id=city_id)
        dest2 = models.Airport.objects.filter(game=self.game, city=city2)[0]
        flight3 = models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=dest2,
            depart_time=time2,
            flight_time=200)

        self.assertEqual(airport.next_flight_to(city, now), flight1)
        airport2 = models.Airport.objects.filter(city=city)[0]
        self.assertEqual(airport.next_flight_to(airport2, now), flight1)
        self.assertEqual(airport.next_flight_to(city2, now), flight3)

        # delay flight1
        flight1.delay(datetime.timedelta(minutes=450), now)
        self.assertEqual(airport.next_flight_to(city, now), flight2)


class CreateFlights(AirportTestBase):
    def runTest(self):
        """test the create flights method"""
        airports = models.Airport.objects.filter(game=self.game)
        airport = random.choice(airports.exclude(
            id=self.game.start_airport.id))
        destinations = airport.destinations.all()

        # we should only have the initial flights that were created at the
        # start point when the game was created
        flights = models.Flight.objects.filter(game=self.game)
        flights = flights.exclude(origin=self.game.start_airport)
        self.assertEqual(flights.count(), 0)

        now = datetime.datetime(2011, 11, 20, 6, 43)
        outgoing = models.Flight.objects.filter(game=self.game,
                                                origin=airport)
        self.assertEqual(outgoing.count(), 0)
        airport.create_flights(now)
        outgoing = models.Flight.objects.filter(game=self.game,
                                                origin=airport)
        self.assertNotEqual(outgoing.count(), 0)

        for flight in outgoing:
            self.assertEqual(flight.origin, airport)
            self.assertNotEqual(flight.destination, airport)
            self.assertTrue(flight.destination in destinations)
            self.assertTrue(flight.depart_time > now)
            self.assertNotEqual(flight.flight_time, 0)


class ToDict(AirportTestBase):
    def setUp(self):
        super(ToDict, self).setUp()
        airports = models.Airport.objects.filter(game=self.game)
        airport = random.choice(airports)
        destination = random.choice(airport.destinations.all())
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        self.flight = models.Flight.objects.create(
            game=self.game,
            origin=airport,
            destination=destination,
            depart_time=depart_time,
            flight_time=flight_time)

    def runTest(self):
        """Test the to_dict() method"""
        flight = self.flight

        now = datetime.datetime(2011, 11, 18, 4, 0)

        d = flight.to_dict(now)
        self.assertEqual(type(d), dict)
        self.assertEqual(sorted(d.keys()), sorted([
            'number', 'depart_time', 'arrival_time', 'destination',
            'id', 'origin', 'status']))
        self.assertEqual(d['status'], 'On Time')

        now = datetime.datetime(2011, 11, 18, 4, 45)
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Boarding')

        flight.delay(datetime.timedelta(minutes=20),
                     datetime.datetime(2011, 11, 18, 4, 0))
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Delayed')

        flight.cancel(now)
        d = flight.to_dict(now)
        self.assertEqual(d['status'], 'Cancelled')


class PlayerTest(AirportTestBase):
    """Test the Player model"""
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


class PurchaseFlight(AirportTestBase):
    @patch('airport.lib.send_message')
    def runTest(self, send_message):
        """Test the purchase_flight() method"""
        player = self.player
        now = datetime.datetime(2011, 11, 20, 7, 13)
        lib.take_turn(self.game, now)
        self.assertEqual(player.airport, self.game.start_airport)
        self.assertEqual(player.ticket, None)

        airport = random.choice(models.Airport.objects.exclude(
            pk=player.airport.pk))
        airport.create_flights(now)
        flight = random.choice(airport.flights.all())

        # assert we can't buy the ticket (flight) if we're not at the airport
        self.assertRaises(models.Flight.NotAtDepartingAirport,
                          player.purchase_flight, flight, now)

        player.airport = airport
        player.save()

        # attempt to buy a flight while in flight
        player.purchase_flight(flight, now)
        now = flight.depart_time
        next_flights = airport.next_flights(now, future_only=True,
                                            auto_create=True)
        flight2 = random.choice(next_flights)
        self.assertRaises(models.Flight.AlreadyDeparted,
                          player.purchase_flight, flight2, now)

        # ok let's land
        now = flight.arrival_time + datetime.timedelta(minutes=1)
        now = lib.take_turn(self.game, now)

        # make sure we have flights
        airport.create_flights(now)

        # lounge around for a while...
        now = now + datetime.timedelta(minutes=60)

        # find a flight that's already departed
        flight3 = random.choice(airport.flights.filter(game=self.game,
                                                       depart_time__lte=now))

        # try to buy it
        self.assertRaises(models.Flight.AlreadyDeparted,
                          player.purchase_flight, flight3, now)


class CurrentGameTest(AirportTestBase):
    """Test the current_game() method in Player"""
    def setUp(self):
        self.players = self._create_players(2)

    def test_no_games_created(self):
        """Test that when there are no games created, current_game is
        None"""
        player = self.players[0]
        self.assertEqual(player.current_game, None)

    def test_game_not_started(self):
        """Test that th when a Game has not yet begun, but the player is in
        the game, returns the Game"""
        player = self.players[0]
        player2 = self.players[1]

        game = models.Game.objects.create_game(host=player, goals=1,
                                               airports=10)
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
    def test_game_over(self, send_message):
        """Test that when a game is over current_game returns the game, but
        status is GAME_OVER"""
        player = self.players[0]
        game = models.Game.objects.create_game(host=player, goals=1,
                                               airports=10)

        game.begin()
        self.assertEqual(player.current_game, game)

        game.end()
        lib.take_turn(game)

        # game should be over
        self.assertEqual(player.current_game, game)
        self.assertEqual(game.state, game.GAME_OVER)


class PerGameAirports(AirportTestBase):
    def setUp(self):
        self.player = self._create_players(1)[0]

    def test_game_has_subset_of_airports(self):
        game = models.Game.objects.create_game(
            host=self.player,
            goals=4,
            airports=10,
            density=2)

        self.assertEqual(game.airports.count(), 10)


class Messages(AirportTestBase):
    """Test the messages model"""

    def setUp(self):
        self.player = self._create_players(1)[0]

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
            messages.append(models.Message.objects.send(
                self.player, 'Test %s' % i))

        self.client.login(username='user1', password='test')
        response = self.client.get(view)
        for message in messages:
            self.assertContains(response, 'data-id="%s"' % message.id)

    def test_finished(self):
        """Test that when finished=False, finishers don't get a message,
        but when finished=True they do"""

        # first, we need a player to finish a game
        player = self.player
        game = models.Game.objects.create_game(host=player, goals=1,
                                               airports=4, density=1)
        game.begin()
        goal = models.Goal.objects.get(game=game)
        models.Message.objects.broadcast('this is test1',
                                         finishers=False)
        messages = models.Message.objects.get_messages(player, read=False)
        self.assertEqual(messages[0].text, 'this is test1')

        # finish
        my_achievement = models.Achievement.objects.get(
            game=game, player=player, goal=goal)
        my_achievement.timestamp = game.time
        my_achievement.save()

        # send a broadcast with finishers=False
        models.Message.objects.broadcast('this is test2', game,
                                         finishers=False)
        messages = models.Message.objects.get_messages(player, read=False)
        self.assertNotEqual(messages[0].text, 'this is test2')

        # send a broadcast with finishers=True
        models.Message.objects.broadcast('this is test3', game, finishers=True)
        messages = models.Message.objects.get_messages(player, read=False)
        self.assertEqual(messages[0].text, 'this is test3')


class ViewTest(AirportTestBase):
    """Test the home view"""
    view = reverse('main')

    def setUp(self):
        self.player, self.player2 = self._create_players(2)


class HomeView(ViewTest):
    def test_not_logged_in(self):
        """Test that you are redirected to the login page when you are not
        logged in
        """
        response = self.client.get(self.view)
        url = reverse('django.contrib.auth.views.login')
        url = url + '?next=%s' % self.view
        self.assertRedirects(response, url)

    def test_game_not_started(self):
        # given the game that has yet to start
        game = models.Game.objects.create_game(
            host=self.player,
            goals=1,
            airports=4,
            density=1
        )
        game.add_player(self.player2)

        # when player2 logs in and goes to the main view
        self.client.login(username=self.player2.username, password='test')
        models.Message.objects.all().delete()
        self.client.get(self.view)

        # Then we get a message saying that the host hasn't started the game yet
        message = models.Message.objects.all()[0]
        message = message.text
        self.assertEqual(message, 'Waiting for user1 to start the game.')

    @patch('airport.lib.send_message')
    def test_new_game(self, send_message):
        """Test that there's no redirect when you're in a new game"""
        player = self.player
        models.Game.objects.create_game(host=player, goals=1,
                                        airports=4, density=1)
        self.client.login(username=player.username, password='test')
        response = self.client.get(self.view)
        self.assertEqual(response.status_code, 200)


class InfoViewTestCase(ViewTest):
    view = reverse('info')

    def test_no_game_redrect(self):
        """When we are not in a game, the JSON response is games_info"""
        player = self.player
        self.client.login(username=player.username, password='test')
        response = self.client.get(self.view)
        json_response = decode_response(response)
        self.assertTrue('current_game' in json_response)
        self.assertEqual(json_response['current_game'], None)

    @patch('airport.lib.send_message')
    def test_finished_game(self, send_message):
        """Test that when you have finished a game, Instead of getting the
        game json you get the games json
        """
        player = self.player
        game = models.Game.objects.create_game(host=player, goals=1,
                                               airports=4, density=1)
        self.client.login(username=player.username, password='test')
        self.client.get(self.view)
        goal = models.Goal.objects.get(game=game)
        my_achievement = models.Achievement.objects.get(
            game=game, player=player, goal=goal)
        my_achievement.timestamp = game.time
        my_achievement.save()
        response = self.client.get(self.view)
        json_response = decode_response(response)
        self.assertEqual(json_response['current_game'], None)

    def test_finished_not_won(self):
        """Like above test, but should apply even if the user isn't the
        winner
        """
        player1 = self.player
        player2 = self.player2

        game = models.Game.objects.create_game(host=player1, goals=1,
                                               airports=4, density=1)
        game.add_player(player2)
        game.begin()
        goal = models.Goal.objects.get(game=game)

        # finish player 1
        my_achievement = models.Achievement.objects.get(
            game=game, player=player1, goal=goal)
        my_achievement.timestamp = game.time
        my_achievement.save()
        self.client.login(username=player1.username, password='test')
        response = self.client.get(self.view)
        json_response = decode_response(response)
        self.assertEqual(json_response['current_game'], None)

        # player 2 still in the game
        self.client.login(username=player2.username, password='test')
        response = self.client.get(self.view)
        json_response = decode_response(response)
        self.assertEqual(json_response['game'], game.pk)

        # finish player 2
        my_achievement = models.Achievement.objects.get(
            game=game, player=player2, goal=goal)
        my_achievement.timestamp = game.time
        my_achievement.save()
        self.client.login(username=player2.username, password='test')
        response = self.client.get(self.view)
        json_response = decode_response(response)
        self.assertEqual(json_response['current_game'], None)

    def test_game_over(self):
        # given the game that has ended
        game = models.Game.objects.create_game(
            host=self.player,
            goals=1,
            airports=4,
            density=1
        )
        game.end()

        # when the player goes to the info view
        self.client.login(username=self.player.username, password='test')
        response = self.client.get(self.view)

        # then he is "redirected" to the game summary view
        json_response = decode_response(response)
        self.assertEqual(
            json_response,
            {'redirect': '/game_summary/?id={0}'.format(game.pk)}
        )

    @patch('airport.views.lib.send_message')
    def test_purchase_flight(self, send_message):
        # given the game that has started
        game = models.Game.objects.create_game(
            host=self.player,
            goals=1,
            airports=4,
            density=1
        )
        game.begin()

        # when the player POSTs to purchase a ticket
        airport = game.start_airport
        flight = airport.next_flights(
            game.time,
            future_only=True,
            auto_create=True
        )[0]
        self.client.login(username=self.player.username, password='test')
        response = self.client.post(self.view, {'selected': flight.pk})

        # Then the ticket gets purchased
        json_response = decode_response(response)
        self.assertEqual(json_response['ticket']['id'], flight.id)

        # And the gameserver is told to throw a wrench
        send_message.assert_called_with('throw_wrench', game.pk)


class RageQuitViewTestCase(ViewTest):
    view = reverse('rage_quit')

    @patch('airport.views.lib.send_message')
    def test_quit(self, send_message):
        # given the game that has started
        game = models.Game.objects.create_game(
            host=self.player,
            goals=1,
            airports=4,
            density=1
        )
        game.begin()

        # when the player POSTs to quit the game
        self.client.login(username=self.player.username, password='test')
        models.Message.objects.all().delete()
        self.client.post(self.view)

        # then we get a message that we left the game
        message = models.Message.objects.all()[0]
        self.assertEqual(
            message.text,
            'You have quit {0}. Wuss!'.format(game)
        )

        # and we are no longer in the game
        game = models.Game.objects.get(pk=game.pk)
        player = game.players.filter(pk=self.player.pk)
        self.assertFalse(player.exists())


class GamesStartViewTestCase(ViewTest):

    view = reverse('start_game')

    @patch('airport.views.lib.send_message')
    def test_host_starts_game(self, send_message):
        # given the game that has not yet started
        host = self.player
        game = models.Game.objects.create_game(
            host=host,
            goals=1,
            airports=4,
            density=1
        )

        # when the host posts to start the game
        self.client.login(username=host.username, password='test')
        response = self.client.post(self.view)

        # then the game starts
        json_response = decode_response(response)
        self.assertEqual(json_response['status'], 'Started')
        game = models.Game.objects.get(pk=game.pk)
        self.assertEqual(game.state, game.IN_PROGRESS)
        send_message.assert_called_with('start_game_thread', game.pk)


class Cities(AirportTestBase):
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
            speed
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
            {models.AirportMaster.objects.get(code='DFW'),
             models.AirportMaster.objects.get(code='DAL')}
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


class ConstantConnections(AirportTestBase):
    def runTest(self):
        """Test that the connection time between two airports is always
        constant (ignoring cancellations/delays and the like"""

        for source in self.game.airports.all():
            for flight in source.create_flights(self.game.time):
                destination = flight.destination
                s2d = flight.flight_time
                d2s = destination.create_flights(self.game.time).filter(
                    destination=source)[0].flight_time

                # We use assertAlmostEqual to compensate for rounding (integer
                # division)
                self.assertAlmostEqual(s2d, d2s, delta=1)


class GamePause(AirportTestBase):
    """Test the pausing/resuming of a game"""
    def setUp(self):
        self.players = self._create_players(2)

    def test_begin_not_paused(self):
        """Test that when you begin a game it is not paused"""
        game = models.Game.objects.create_game(self.players[0], 1, 10)
        game.begin()

        self.assertNotEqual(game.state, game.PAUSED)

    def test_pause_method(self):
        """Test the pause method"""
        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
        game.begin()
        game.pause()

        self.assertEqual(game.state, game.PAUSED)

    def test_game_time_doesnt_change(self):
        """Test that the game time doesn't change when paused"""
        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
        game.begin()
        game.pause()
        orig_time = game.time
        time.sleep(1)
        new_time = game.time
        self.assertEqual(orig_time, new_time)

    def test_info_view(self):
        """Test the info view of a paused game"""
        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
        game.begin()
        game.pause()

        self.client.login(username=self.players[0].username, password='test')
        response = self.client.get(reverse('info'))
        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response['game_state'], 'Paused')

    def test_ticket_purchase(self):
        """Ensure you can't purchase tickets on a paused game"""
        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
        game.begin()
        game.pause()

        airport = game.start_airport
        flights = airport.next_flights(game.time, future_only=True)
        flight = flights[0]

        self.assertRaises(
            game.Paused,
            self.players[0].purchase_flight,
            flight,
            game.time
        )

    @patch('airport.lib.send_message')
    def test_in_flight(self, send_message):
        """Test that you are paused in-flight"""

        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
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
        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
        game.begin()
        game.pause()

        game.add_player(self.players[1])
        self.assertEqual(set(game.players.filter(ai_player=False)),
                         set([self.players[0], self.players[1]])
                         )

    def test_active_game_status(self):
        """Assert that the game status shows the game as paused"""
        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
        game.begin()
        game.pause()

        user2 = self.players[1]
        self.client.login(username=user2.username, password='test')
        response = self.client.get(reverse('games_info'))
        response = json.loads(response.content.decode('utf-8'))
        response_game = list(filter(lambda x: x['id'] == game.id,
                                    response['games']))[0]

        self.assertEqual(response_game['status'], 'Paused')

    def test_resume(self):
        """Assert that resume works and the time doesn't fast-forward"""
        game = models.Game.objects.create_game(host=self.players[0],
                                               goals=1, airports=10)
        game.begin()
        game.pause()

        orig_time = game.time
        time.sleep(3)
        game.resume()
        new_time = game.time
        time_difference_secs = (new_time - orig_time).total_seconds()
        self.assertTrue(time_difference_secs < game.TIMEFACTOR)


class AIPlayerTest(AirportTestBase):
    def test_ai_player_optional(self):
        """AI Player is optional"""
        self.game.end()
        game = models.Game.objects.create_game(
            ai_player=True,
            host=self.player,
            goals=1,
            airports=10
        )

        ai_player = game.players.filter(ai_player=True)
        self.assertTrue(ai_player.exists())
        game.end()

        game = models.Game.objects.create_game(
            ai_player=False,
            host=self.player,
            goals=1,
            airports=10
        )

        ai_player = game.players.filter(ai_player=True)
        self.assertFalse(ai_player.exists())

    @patch('airport.lib.send_message')
    def test_view(self, send_message):
        url = reverse('airport.views.games_create')
        self.game.end()

        self.client.login(username='user1', password='test')

        # first try with an ai player
        form = {
            'goals': 1,
            'airports': 20,
            'ai_player': 'Yes'
        }

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
        form = {
            'goals': 1,
            'airports': 20,
            'ai_player': 'No'
        }

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
            ai_player=True,
            host=self.player,
            goals=1,
            airports=10
        )
        ai_player = game.players.get(ai_player=True)

        # When only one flight is outbound
        game.begin()
        airport = game.start_airport
        now = lib.take_turn(game)
        flights_out = airport.next_flights(now, future_only=True,
                                           auto_create=False)
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


class GameServerTest(AirportTestBase):
    def setUp(self):
        super(GameServerTest, self).setUp()
        self.messages = []

    def send_message(self, message_type, data):
        if message_type == 'info':
            self.messages.append(data)

    @patch('airport.lib.send_message')
    def test_does_not_show_finished_on_new_game(self, send_message):
        # when we finish our first game
        self.game.begin()
        now = self.game.time

        # to finish the game, we cheat a bit
        ach = models.Achievement.objects.get(player=self.player,
                                             game=self.game)
        ach = ach.fulfill(now)
        self.assertTrue(self.player.finished(self.game))

        # when we join a new game
        game = models.Game.objects.create_game(
            ai_player=True,
            host=self.player,
            goals=1,
            airports=10
        )
        game.begin()

        # and the original game takes a turn
        send_message.side_effect = self.send_message
        lib.take_turn(self.game)

        # we don't get any info messages wrt the original game
        for message in self.messages:
            if message['player'] != self.player.username:
                continue
            game_id = message['game']
            self.assertNotEqual(game_id, self.game.pk)

    @patch('airport.lib.send_message')
    def test_force_quit_game(self, send_message):
        # start the game server
        lib.start_game(self.game)
        management.call_command('gameserver', forcequit=self.game.pk)
        # re-fetch the model
        game = models.Game.objects.get(pk=self.game.pk)
        self.assertEqual(game.state, game.GAME_OVER)

    @patch('airport.lib.send_message')
    def test_pause_game(self, send_message):
        """We can pause a game"""
        # Given the players and games
        game1 = self.game
        user2 = User.objects.create_user(username='test2', password='test')
        player2 = models.Player.objects.create(user=user2)
        game2 = models.Game.objects.create_game(
            host=player2,
            goals=3,
            airports=15
        )
        lib.start_game(game1)
        lib.start_game(game2)

        # When we pause a game from the managment command
        management.call_command('gameserver', pause=game1.pk)

        # Then that game is paused
        # (re-fetch)
        game1 = models.Game.objects.get(pk=game1.pk)
        game2 = models.Game.objects.get(pk=game2.pk)

        self.assertEqual(game1.state, game1.PAUSED)
        self.assertEqual(game2.state, game2.IN_PROGRESS)

        # Calling with "--resume" resumes the game
        management.call_command('gameserver', resume=game1.pk)
        # (re-fetch)
        game1 = models.Game.objects.get(pk=game1.pk)
        game2 = models.Game.objects.get(pk=game2.pk)
        self.assertEqual(game1.state, game1.IN_PROGRESS)
        self.assertEqual(game2.state, game2.IN_PROGRESS)

        # Calling --pause with id=0 pauses all active games
        management.call_command('gameserver', pause=0)

        for game in models.Game.objects.exclude(state__gt=0):
            self.assertEqual(game.state, game.PAUSED)

        # Calling --resume with id=0 resumes all active games
        management.call_command('gameserver', resume=0)

        for game in models.Game.objects.exclude(state__gt=0):
            self.assertEqual(game.state, game.IN_PROGRESS)

    @patch('airport.lib.send_message')
    def test_create_game(self, send_message):
        """Create a game through the management command"""
        self.game.end()
        games = models.Game.objects.filter(host=self.player,
                                           state=models.Game.IN_PROGRESS)
        self.assertFalse(games.exists())
        management.call_command('gameserver', creategame=self.player.username)

        games = models.Game.objects.filter(host=self.player,
                                           state=models.Game.IN_PROGRESS)
        self.assertTrue(games.exists())

    @patch('airport.lib.send_message')
    def test_create_game_with_args(self, send_message):
        """Create a game using --create user:airports:goals"""
        self.game.end()
        num_airports = 19
        arg = '{0}:{1}'.format(self.player.username, num_airports)
        management.call_command('gameserver', creategame=arg)
        games = models.Game.objects.filter(host=self.player,
                                           state=models.Game.IN_PROGRESS)
        self.assertTrue(games.exists())
        game = games[0]
        self.assertEqual(game.host, self.player)
        self.assertEqual(game.airports.count(), num_airports)
        self.assertEqual(game.goals.count(), 3)  # default

        # now try it specifying the goals too
        game.end()
        num_airports = 91
        num_goals = 14
        arg = '{0}:{1}:{2}'.format(
            self.player.username,
            num_airports,
            num_goals,
        )
        management.call_command('gameserver', creategame=arg)
        games = models.Game.objects.filter(host=self.player,
                                           state=models.Game.IN_PROGRESS)
        self.assertTrue(games.exists())
        game = games[0]
        self.assertEqual(game.host, self.player)
        self.assertEqual(game.airports.count(), num_airports)
        self.assertEqual(game.goals.count(), num_goals)


class CreateGameTest(AirportTestBase):
    """Tests for the create_game() method"""
    def test_with_start_airport(self):
        self.game.end()

        # given the start airport
        masters = models.AirportMaster.objects.all().order_by('?')
        start_airport = masters[0]

        # When we call create_airport telling it to start there
        game = models.Game.objects.create_game(
            self.player,
            1,
            10,
            ai_player=False,
            start=start_airport
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


################################################################################
# MonkeyWrenches                                                               #
################################################################################
class MonkeyWrenchTestBase(AirportTestBase):
    def setUp(self):
        super(MonkeyWrenchTestBase, self).setUp()

        # Fill in the flights
        self.now = self.game.time
        for airport in self.game.airports.all():
            airport.next_flights(self.now, future_only=True, auto_create=True)


class MonkeyWrenchTest(MonkeyWrenchTestBase):
    def test_str(self):
        # Given the MonkeyWrench
        now = self.game.time
        mw = monkeywrench.MonkeyWrench(self.game, now)

        # When we call str() on it
        result = str(mw)

        # Then we get the expected result
        self.assertEqual(result, 'MonkeyWrench: MonkeyWrench')

    def test_throw(self):
        now = self.game.time
        mw = monkeywrench.MonkeyWrench(self.game, now)

        # When we throw() it
        mw.throw()

        # Then it gets thrown
        self.assertTrue(mw.thrown)

    def test_now_property(self):
        now = self.game.time
        mw = monkeywrench.MonkeyWrench(self.game, now)

        # When we access the now property
        mw_now = mw.now

        # Then we get the game time
        self.assertEqual(mw_now, now)


class CancelledFlightMonkeyWrenchTest(MonkeyWrenchTestBase):
    def test_throw(self):
        # Given the CancelledFlight monkeywrench
        mw = monkeywrench.CancelledFlight(self.game)

        # When it's thrown
        mw.throw()

        # Then a flight gets cancelled
        cancelled = models.Flight.objects.filter(game=self.game,
                                                 state='Cancelled')
        self.assertTrue(mw.thrown)
        self.assertTrue(cancelled.exists())


class DelayedFlightMonkeyWrenchTest(MonkeyWrenchTestBase):
    def test_throw(self):
        # given the monkeywrench
        mw = monkeywrench.DelayedFlight(self.game)

        # when it's thrown
        mw.throw()

        # then a flight gets delayed
        delayed = models.Flight.objects.filter(game=self.game, state='Delayed')
        self.assertEqual(delayed.count(), 1)
        self.assertTrue(mw.thrown)


class AllFlightsFromAirportDelayedMonkeyWrenchTest(MonkeyWrenchTestBase):
    def test_throw(self):
        # given the monkeywrench
        mw = monkeywrench.AllFlightsFromAirportDelayed(self.game, self.now)

        # when it's thrown
        mw.throw()

        # Then all flights from an airport are delayed
        self.assertTrue(mw.thrown)
        delayed_flights = models.Flight.objects.filter(
            depart_time__gt=self.now,
            state='Delayed',
            game=self.game
        )
        airport = delayed_flights[0].origin
        airport_flights = models.Flight.objects.filter(
            depart_time__gt=self.now,
            game=self.game,
            origin=airport
        )

        for flight in airport_flights:
            self.assertEqual(flight.state, 'Delayed')


class AllFlightsFromAirportCancelledMonkeyWrenchTest(MonkeyWrenchTestBase):
    def test_throw(self):
        # given the monkeywrench
        mw = monkeywrench.AllFlightsFromAirportCancelled(self.game, self.now)

        # when it's thrown
        mw.throw()

        # Then all flights from an airport are cancelled
        self.assertTrue(mw.thrown)
        delayed_flights = models.Flight.objects.filter(
            depart_time__gt=self.now,
            state='Cancelled',
            game=self.game
        )
        airport = delayed_flights[0].origin
        airport_flights = models.Flight.objects.filter(
            depart_time__gt=self.now,
            game=self.game,
            origin=airport
        )

        for flight in airport_flights:
            self.assertEqual(flight.state, 'Cancelled')


class HintMonkeyWrenchTest(MonkeyWrenchTestBase):
    """Hint MonkeyWrench"""
    def test_throw(self):
        # given the monkeywrench
        mw = monkeywrench.Hint(self.game)

        # when it's thrown
        # First, we remove the ai player because if he get's the MW then the
        # message is not sent
        ai_player = self.game.players.get(ai_player=True)
        self.game.remove_player(ai_player)

        models.Message.objects.all().delete()
        mw.throw()

        # Then the player gets a hint
        self.assertTrue(mw.thrown)
        messages = models.Message.objects.all()
        last_message = messages[0]
        text = last_message.text
        self.assertTrue(text.startswith('Hint: '))


class FullFlightMonkeyWrenchTest(MonkeyWrenchTestBase):
    """FullFlight MonkeyWrench()"""
    def test_throw(self):
        # given the FullFlight monkeywrench
        mw = monkeywrench.FullFlight(self.game, self.now)

        # when we throw it
        mw.throw()

        # then a flight fills
        self.assertTrue(mw.thrown)
        flights = models.Flight.objects.filter(
            game=self.game,
            depart_time__gt=self.now,
            full=True
        )
        self.assertEqual(flights.count(), 1)


class TSAMonkeyWrenchTest(MonkeyWrenchTestBase):
    """TSA MonkeyWrench"""
    def test_trow(self):
        # Given the monkeywrench
        mw = monkeywrench.TSA(self.game, self.now)
        mw.minutes_before_departure = 60

        # and the flight taking off within 60 minutes
        flight = models.Flight.objects.filter(
            game=self.game,
            depart_time__gt=self.now,
            depart_time__lte=self.now + datetime.timedelta(minutes=60),
            origin=self.game.start_airport
        )[0]

        # when a player purches the flight
        self.player.purchase_flight(flight, self.now)
        self.assertTrue(self.player.ticket)

        # and the wrench is thrown
        models.Message.objects.all().delete()
        mw.throw()

        # then said player gets booted
        self.assertTrue(mw.thrown)

        player = models.Player.objects.get(pk=self.player.pk)
        self.assertEqual(player.ticket, None)

        message = models.Message.objects.all()[0]
        message = message.text
        self.assertEqual(
            message,
            ('Someone reported you as suspicious and you have been removed'
             ' from the plane.')
        )


class TailWindMonkeyWrenchTest(AirportTestBase):
    """HeadWind wrench."""
    @patch('airport.lib.send_message')
    def test_TailWind(self, send_message):
        # let's make sure at least one flight is in the air
        self.game.begin()
        now = lib.take_turn(self.game, throw_wrench=False)
        airport = self.game.start_airport
        flights_out = airport.next_flights(now, future_only=True,
                                           auto_create=False)

        flights_out.sort(key=lambda x: x.depart_time)
        flight = flights_out[0]
        now = flight.depart_time + datetime.timedelta(minutes=1)

        # crash all the other flights
        crashed = models.Flight.objects.filter(game=self.game)
        crashed.exclude(pk=flight.pk).delete()

        wrench = monkeywrench.TailWind(self.game, now)
        flights_in_air = models.Flight.objects.in_flight(self.game, now)
        self.assertEqual([flight], list(flights_in_air))

        # when the wrench is thrown
        original_time = flight.arrival_time
        wrench.throw()
        self.assertTrue(wrench.thrown)

        # then the flight's arrival_time changed
        flight = models.Flight.objects.get(pk=flight.pk)
        self.assertGreater(original_time, flight.arrival_time)


def decode_response(response):
    """Take a response object and return the json-decoded content"""
    assert response.status_code == 200
    assert response['content-type'] == 'application/json'
    content = response.content
    content = content.decode(response._charset)
    return json.loads(content)
