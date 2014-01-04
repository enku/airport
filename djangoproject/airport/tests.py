import datetime
import json
import random
import time

from django.contrib.auth.models import User
from django.core import management
from django.core.urlresolvers import reverse
from django.test import TestCase, TransactionTestCase
from mock import patch

from airport import lib
from airport import models
from airport import monkeywrench as mw


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
    def runTest(self):
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


class HomeViewTest(AirportTestBase):
    """Test the home view"""
    view = reverse('home')

    def setUp(self):
        self.player, self.player2 = self._create_players(2)


class HomeViewNotLoggedIn(HomeViewTest):
    def runTest(self):
        """Test that you are redirected to the login page when you are not
        logget in"""
        response = self.client.get(self.view)
        url = reverse('django.contrib.auth.views.login')
        url = url + '?next=%s' % self.view
        self.assertRedirects(response, url)


class HomeViewNoGameRedirect(HomeViewTest):
    def runTest(self):
        """test that when you are not in a game, you are redirected to the
        games page"""
        player = self.player
        games_view = reverse('games')
        self.client.login(username=player.username, password='test')
        response = self.client.get(self.view)
        self.assertRedirects(response, games_view)


class HomeViewNewGame(HomeViewTest):
    @patch('airport.lib.send_message')
    def runTest(self, send_message):
        """Test that there's no redirect when you're in a new game"""
        player = self.player
        models.Game.objects.create_game(host=player, goals=1,
                                        airports=4, density=1)
        self.client.login(username=player.username, password='test')
        response = self.client.get(self.view)
        self.assertEqual(response.status_code, 200)


class HomeViewFinishedGame(HomeViewTest):
    @patch('airport.lib.send_message')
    def runTest(self, send_message):
        """Test that when you have finished a game, you are redirected"""
        player = self.player
        games_view = reverse('games')
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
        self.assertRedirects(response, games_view)


class FinishedNotWon(HomeViewTest):
    def runTest(self):
        """Like above test, but should apply even if the user isn't the
        winner"""
        player1 = self.player
        player2 = self.player2
        games_view = reverse('games')

        game = models.Game.objects.create_game(host=player1, goals=1,
                                               airports=4, density=1)
        game.add_player(player2)
        game.begin()
        goal = models.Goal.objects.get(game=game)

        #finish player 1
        my_achievement = models.Achievement.objects.get(
            game=game, player=player1, goal=goal)
        my_achievement.timestamp = game.time
        my_achievement.save()
        self.client.login(username=player1.username, password='test')
        response = self.client.get(self.view)
        self.assertRedirects(response, games_view)

        #player 2 still in the game
        self.client.login(username=player2.username, password='test')
        response = self.client.get(self.view)
        self.assertEqual(response.status_code, 200)

        # finish player 2
        my_achievement = models.Achievement.objects.get(
            game=game, player=player2, goal=goal)
        my_achievement.timestamp = game.time
        my_achievement.save()
        self.client.login(username=player2.username, password='test')
        response = self.client.get(self.view)
        self.assertRedirects(response, games_view)


class Cities(AirportTestBase):
    """Test the Cities module"""
    def runTest(self):
        """Test that all cities have images"""
        for city in models.City.objects.all():
            self.assertNotEqual(city.image, None)


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
            'ai_player': True
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
            'ai_player': False
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


class MonkeyWrenchTest(AirportTestBase):

    """Tests for Monkey wrenches."""
    @patch('airport.lib.send_message')
    def test_TailWind(self, send_message):
        """HeadWind wrench."""
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

        wrench = mw.TailWind(self.game, now)
        flights_in_air = models.Flight.objects.in_flight(self.game, now)
        self.assertEqual([flight], list(flights_in_air))

        # when the wrench is thrown
        original_time = flight.arrival_time
        wrench.throw()
        self.assertTrue(wrench.thrown)

        # then the flight's arrival_time changed
        flight = models.Flight.objects.get(pk=flight.pk)
        self.assertGreater(original_time, flight.arrival_time)


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
