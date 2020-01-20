"""
Tests for the airport app
"""
import datetime
import json
from unittest.mock import Mock, call, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core import management
from django.core.urlresolvers import reverse
from django.test import TestCase
from tornado import gen
from tornado.concurrent import Future
from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import Application
from tornado.websocket import WebSocketHandler, websocket_connect

from airport import lib
from airport import models as db
from airport.tests import BaseTestCase

MINUTE = datetime.timedelta(seconds=60)


# copied from tornado's websocket_test.py
class WebSocketBaseTestCase(AsyncHTTPTestCase):
    @gen.coroutine
    def ws_connect(self, path, compression_options=None):
        ws = yield websocket_connect(
            'ws://127.0.0.1:%d%s' % (self.get_http_port(), path),
            compression_options=compression_options,
        )
        raise gen.Return(ws)

    @gen.coroutine
    def close(self, ws):
        """Close a websocket connection and wait for the server side.
        If we don't wait here, there are sometimes leak warnings in the
        tests.
        """
        ws.close()
        yield self.close_future


@patch('airport.lib.IPCHandler.send_message')
class StartGameTestCase(BaseTestCase):

    """tests for the start_game function"""

    def test_starts_game(self, mock_send_msg):
        # given the game
        game = self.game

        # when we call start_game() on it
        lib.start_game(game)

        # then the game begins
        self.assertEqual(game.state, game.IN_PROGRESS)

    def test_starts_sends_message(self, mock_send_msg):
        # given the game
        game = self.game

        # when we call start_game() on it
        lib.start_game(game)

        # then a message is sent to the gameserver via ipc
        expected = call.send_message('start_game', game.pk)
        mock_send_msg.assert_has_calls([expected])


@patch('airport.lib.IPCHandler.send_message')
class TakeTurn(BaseTestCase):

    """Tests for the take_turn function"""

    def test_does_nothing_if_game_not_running(self, mock_send_msg):
        # given the game
        game = self.game

        # when the game is paused and we call take_turn()
        game.pause()
        now = game.time
        new_now = lib.take_turn(game, now=now)

        # then nothing happens
        self.assertEqual(now, new_now)

    def test_throw_wrench(self, mock_send_msg):
        # given the game in progress
        game = self.game
        game.begin()

        # when we call take_turnw(throw_wrench=True)
        lib.take_turn(game, throw_wrench=True)

        # then a message to throw a wrench is sent
        expected = call.send_message('throw_wrench', game.pk)
        mock_send_msg.assert_has_calls([expected])

    @patch('airport.lib.handle_flights')
    def test_handles_flights(self, mock_handle_flights, mock_send_msg):
        # given the game in progress
        game = self.game
        game.begin()

        # when we call take_turn()
        lib.take_turn(game)

        # then it calls handle_flights
        self.assertTrue(mock_handle_flights.called)

    @patch('airport.lib.handle_players')
    def test_handles_players(self, mock_handle_players, mock_send_msg):
        # given the game in progress
        game = self.game
        game.begin()

        # when we call take_turn()
        lib.take_turn(game)

        # then it calls handle_players
        self.assertTrue(mock_handle_players.called)

    def test_advances_game_time(self, mock_send_msg):
        # given the game in progress
        game = self.game
        game.begin()

        # when we call take_turn()
        now = game.time
        game_time = lib.take_turn(game)

        # then the game time advances
        self.assertGreater(game_time, now)


@patch('airport.lib.IPCHandler.send_message')
class HandleFlightsTestCase(BaseTestCase):

    """tests for the handle_flights() function"""

    def test_handles_departing_flight_player(self, mock_send_msg):
        # given the game and player

        game = self.game
        player = self.player
        game.begin()

        # when the player has purchased a flight
        now = lib.take_turn(game)
        airport = game.start_airport
        flight = db.Flight.objects.filter(
            game=game, origin=airport, depart_time__gt=now
        )[0]
        ticket = player.purchase_flight(flight, now)
        assert player.airport

        # and handle_flights is called after which point the flight should
        # depart
        time = flight.depart_time + 1 * MINUTE
        lib.handle_flights(game, airport, now=time)

        # then the player is put in flight
        self.assertTrue(player.location(time), (None, ticket))

    def test_handles_departing_flight_purchase_recorded(self, mock_send_msg):

        # given the game and player
        game = self.game
        player = self.player
        game.begin()

        # when the player has purchased a flight
        now = lib.take_turn(game)
        airport = game.start_airport
        flight = db.Flight.objects.filter(
            game=game, origin=airport, depart_time__gt=now
        )[0]
        player.purchase_flight(flight, now)

        # and handle_flights is called after which point the flight should
        # depart
        time = flight.depart_time + 1 * MINUTE
        lib.handle_flights(game, airport, now=time)

        # then the ticket purchase is recorded
        purchase = db.Purchase.objects.filter(player=player, game=game, flight=flight)
        self.assertTrue(purchase.exists())

    @patch('airport.lib.models.Message.objects.announce')
    def test_handles_departing_flight_announcement(self, mock_ann, mock_send_msg):

        # given the game and player
        game = self.game
        player = self.player
        game.begin()

        # when the player has purchased a flight
        now = lib.take_turn(game)
        airport = game.start_airport
        flight = db.Flight.objects.filter(
            game=game, origin=airport, depart_time__gt=now
        )[0]
        player.purchase_flight(flight, now)

        # and handle_flights is called after which point the flight should
        # depart
        time = flight.depart_time + 1 * MINUTE
        lib.handle_flights(game, airport, now=time)

        # then an announcement is made the the player has left
        announce_msg = mock_ann.mock_calls[0][1][1]  # trust me
        expected = '%s has departed %s.' % (player.username, airport)
        self.assertEqual(announce_msg, expected)

    def test_handles_arriving_flights_players_arrived(self, mock_send_msg):

        # given the game and player
        game = self.game
        player = self.player
        game.begin()

        # when the player has purchased a flight
        now = lib.take_turn(game)
        airport = game.start_airport
        flight = db.Flight.objects.filter(
            game=game, origin=airport, depart_time__gt=now
        )[0]
        player.purchase_flight(flight, now)

        # and handle_flights is called after which point the flight should
        # have arrived
        time = flight.arrival_time + 1 * MINUTE
        airport = flight.destination
        result = lib.handle_flights(game, airport, now=time)

        # then the player is returned in the list of arrivals
        self.assertTrue(player in result)

    @patch('airport.lib.models.Message.objects.announce')
    def test_handles_arriving_flights_announcement(self, mock_ann, mock_send_msg):

        # given the game and player
        game = self.game
        player = self.player
        game.begin()

        # when the player has purchased a flight
        now = lib.take_turn(game)
        airport = game.start_airport
        flight = db.Flight.objects.filter(
            game=game, origin=airport, depart_time__gt=now
        )[0]
        player.purchase_flight(flight, now)

        # and handle_flights is called after which point the flight should
        # have arrived
        time = flight.arrival_time + 1 * MINUTE
        airport = flight.destination
        lib.handle_flights(game, airport, now=time)

        # then an announcement is made the the player has arrived
        announce_msg = mock_ann.mock_calls[0][1][1]  # trust me
        expected = '%s has arrived at %s.' % (player.username, airport)
        self.assertEqual(announce_msg, expected)

    def test_handles_arriving_player_updated(self, mock_send_msg):

        # given the game and player
        game = self.game
        player = self.player
        game.begin()

        # when the player has purchased a flight
        now = lib.take_turn(game)
        airport = game.start_airport
        flight = db.Flight.objects.filter(
            game=game, origin=airport, depart_time__gt=now
        )[0]
        player.purchase_flight(flight, now)

        # and handle_flights is called after which point the flight should
        # have arrived
        time = flight.arrival_time + 1 * MINUTE
        airport = flight.destination
        lib.handle_flights(game, airport, now=time)

        # then the player's location is changed and ticket removed
        # (refetch-from the db)
        player = db.Player.objects.get(pk=player.pk)
        self.assertEqual(player.airport, airport)
        self.assertEqual(player.ticket, None)

    def test_handles_arriving_achievement(self, mock_send_msg):

        # given the game and player
        game = self.game
        player = self.player
        game.begin()

        # when the player is at an airport that has a flight to her first goal
        # (warning: lots of voodoo here)
        goal_city = game.goals.all()[0]
        goal_city_airport = db.Airport.objects.get(game=game, master__city=goal_city)
        origin_airport = db.Airport.objects.filter(destinations=goal_city_airport)[0]

        # place the player there
        player.airport = origin_airport
        player.save()

        # buy a flight to the destination
        now = lib.take_turn(game)
        flight = db.Flight.objects.filter(
            game=game,
            origin=origin_airport,
            destination=goal_city_airport,
            depart_time__gt=now,
        )[0]
        player.purchase_flight(flight, now)

        # when handle_flights is called after which point the flight should
        # have arrived
        time = flight.arrival_time + 1 * MINUTE
        lib.handle_flights(game, goal_city_airport, now=time)

        # then the player's achievement is marked
        goal = db.Goal.objects.get(city=goal_city, game=game, order=1)
        ach = db.Achievement.objects.get(goal=goal, player=player, game=game)
        self.assertEqual(ach.timestamp, flight.arrival_time)


@patch('airport.lib.IPCHandler.send_message')
class HandlePlayersTestCase(BaseTestCase):

    """tests for the lib.handle_players() function"""

    def test_player_has_arrived(self, mock_send_msg):

        # given the game
        game = self.game
        game.begin()

        # and a recently arrived player
        player = self.player
        now = lib.take_turn(game)
        flight = db.Flight.objects.filter(
            game=game, origin=game.start_airport, depart_time__gt=now
        )[0]
        player.purchase_flight(flight, now)

        # when we call handle_players()
        mock_send_msg.reset_mock()
        time = flight.arrival_time + 1 * MINUTE
        lib.handle_players(game, time, [], {player.pk: flight.destination})

        # then the player is sent an ipc message saying she has arrived
        args = [i[0] for i in mock_send_msg.call_args_list]
        args = [i for i in args if i[0] == 'info']
        expected = 'You have arrived at {city.name}.'
        expected = expected.format(city=flight.destination.city)
        self.assertTrue(any([i[1]['notify'] == expected for i in args]))

    def test_player_info(self, mock_send_msg):
        # given the game
        game = self.game

        # when we call handle_players()
        now = game.time
        lib.handle_players(game, now, [], [])

        # then an 'info' ipc message is sent for each player
        game_players = game.players.distinct()
        game_players = set([i.username for i in game_players])
        call_args = mock_send_msg.call_args_list
        call_args = [i[0] for i in call_args]  # no need for kwargs
        call_args = [i for i in call_args if i[0] == 'info']
        players = set([i[1]['player'] for i in call_args])
        self.assertEqual(game_players, players)

    @patch('airport.lib.models.Message.objects.broadcast')
    def test_winner(self, mock_broadcast, mock_send_msg):

        # given the game
        game = self.game
        game.begin()

        # and a player who has won the game
        player = self.player
        # basically I'm going to mock winning the game, because I'm too lazy to
        # set up all the pieces:
        with patch('airport.lib.models.Player.objects.winners') as m_winners:
            m_winners.return_value = db.Player.objects.filter(pk=player.pk)

            # when we call handle_players
            winners_before = []
            goal = game.goals.all()[0]
            goal_airport = db.Airport.objects.filter(game=game, master__city=goal)[0]
            arrivals = {player.pk: goal_airport}
            lib.handle_players(game, game.time, winners_before, arrivals)

        # Then a message saying the user has won the game is broadcast
        msg = '{player.username} has won {game}.'
        msg = msg.format(player=player, game=game)
        expected = call(msg, game, finishers=True, message_type='WINNER')
        self.assertTrue(expected in mock_broadcast.mock_calls)

    @patch('airport.lib.models.Message.objects.broadcast')
    def test_winner_tie(self, mock_broadcast, mock_send_msg):

        # given the game
        game = self.game
        game.begin()

        # and a both players have tied the game
        players = game.players.distinct()
        with patch('airport.lib.models.Player.objects.winners') as m_winners:
            m_winners.return_value = players

            # when we call handle_players
            winners_before = []
            goal = game.goals.all()[0]
            goal_airport = db.Airport.objects.filter(game=game, master__city=goal)[0]
            arrivals = {player.pk: goal_airport for player in players}
            lib.handle_players(game, game.time, winners_before, arrivals)

        # Then a flurry of messages announcing the call is sent
        calls = [
            call(
                '%s: 2-way tie for 1st place.' % game,
                game,
                finishers=True,
                message_type='WINNER',
            ),
            call(
                '%s is a winner!' % players[0].username,
                game,
                finishers=True,
                message_type='WINNER',
            ),
            call(
                '%s is a winner!' % players[1].username,
                game,
                finishers=True,
                message_type='WINNER',
            ),
        ]
        mock_broadcast.assert_has_calls(calls)

    def test_game_over_sends_message(self, mock_send_msg):
        # given the game that is over
        game = self.game
        # (the quickest way to end a game is to eject all it's players)
        players = game.players.distinct()
        for player in players:
            game.remove_player(player)

        # when we call handle_players()
        now = game.time
        lib.handle_players(game, now, [], [])

        # then a game_over ipc message is sent
        expected = call('game_ended', game.pk)
        self.assertTrue(expected in mock_send_msg.mock_calls)

    def test_over_ends_game(self, mock_send_msg):

        # given the game that is over
        game = self.game
        # (the quickest way to end a game is to eject all it's players)
        players = game.players.distinct()
        for player in players:
            game.remove_player(player)

        # when we call handle_players()
        now = game.time
        lib.handle_players(game, now, [], [])

        # then the game is officially ended
        game = db.Game.objects.get(pk=game.pk)  # need to re-fetch
        self.assertEqual(game.state, game.GAME_OVER)


@patch('airport.lib.IPCHandler.send_message')
class GamePauseTestCase(BaseTestCase):

    """tests for the game_pause() function"""

    def test_game_already_paused(self, mock_send_msg):
        # given the game that is already paused
        game = self.game
        game.begin()
        game.pause()

        # when we call game_pause()
        result = lib.game_pause(game)

        # then the result returned is that the game is paused
        self.assertEqual(result['game_state'], 'Paused')

        # but no message is sent to the players
        self.assertEqual(mock_send_msg.call_count, 0)

    def test_game_running(self, mock_send_msg):

        # given the game that is running
        game = self.game
        game.begin()

        # when we call game_pause()
        result = lib.game_pause(game)

        # then the result returned is that the game is paused
        self.assertEqual(result['game_state'], 'Paused')

        # and indeed it is
        pk = game.pk
        game = db.Game.objects.get(pk=pk)
        self.assertEqual(game.state, game.PAUSED)

        # and each player gets sent a message that the game is paused
        players = set(game.players.distinct())
        call_args_list = mock_send_msg.call_args_list
        info_calls = [i for i in call_args_list if i[0][0] == 'info']
        info_calls = [(i[0][1]['player'], i[0][1]['game_state']) for i in info_calls]
        info_calls = set(info_calls)
        expected = set([(i.username, 'Paused') for i in players])
        self.assertEqual(info_calls, expected)

    def test_game_already_over(self, mock_send_msg):

        # given the game that has already ended
        game = self.game
        game.begin()
        game.end()  # ... it was over just as soon as it began :(

        # when we call game_pause()
        result = lib.game_pause(game)

        # then the result returned is that the game is over
        self.assertEqual(result['game_state'], 'Finished')

        # and indeed it is
        pk = game.pk
        game = db.Game.objects.get(pk=pk)
        self.assertEqual(game.state, game.GAME_OVER)

        # and each player gets sent a message that the game is over
        players = set(game.players.distinct())
        call_args_list = mock_send_msg.call_args_list
        info_calls = [i for i in call_args_list if i[0][0] == 'info']
        info_calls = [(i[0][1]['player'], i[0][1]['game_state']) for i in info_calls]
        info_calls = set(info_calls)
        expected = set([(i.username, 'Finished') for i in players])
        self.assertEqual(info_calls, expected)


@patch('airport.lib.IPCHandler.send_message')
class GameResumeTestCase(BaseTestCase):

    """tests for the game_resume() function"""

    def test_game_not_paused(self, mock_send_msg):

        # given the game that isn't paused
        game = self.game
        game.begin()

        # when we call game_resume() on it
        result = lib.game_resume(game)

        # then the game retains state
        pk = game.pk
        game = db.Game.objects.get(pk=pk)
        self.assertEqual(game.state, game.IN_PROGRESS)

        # the appropriate info is returned
        self.assertEqual(result['game_state'], 'Started')

        # but nothing is sent to the players
        num_msgs = mock_send_msg.call_count
        self.assertEqual(num_msgs, 0)

    def test_messages_sent_to_players(self, mock_send_msg):

        # given the game that's paused
        game = self.game
        game.begin()
        game.pause()

        # when we call game_resume() on it
        result = lib.game_resume(game)

        # then the game gets resumed
        pk = game.pk
        game = db.Game.objects.get(pk=pk)
        self.assertEqual(game.state, game.IN_PROGRESS)

        # and the appropriate info is returned
        self.assertEqual(result['game_state'], 'Started')

        # and an info gets sent to all the players
        players = set(game.players.distinct())
        call_args_list = mock_send_msg.call_args_list
        info_calls = [i for i in call_args_list if i[0][0] == 'info']
        info_calls = [(i[0][1]['player'], i[0][1]['game_state']) for i in info_calls]
        info_calls = set(info_calls)
        expected = set([(i.username, 'Started') for i in players])
        self.assertEqual(info_calls, expected)


@patch('airport.lib.IPCHandler.send_message')
class SendMessageTestCase(TestCase):

    """test for the send_message() function"""

    def test_sends_message(self, mock_send_message):
        # when we call the send_message() function
        message_type = 'info'
        data = 'Whatever'
        lib.send_message(message_type, data)

        # then the arguments get send to IPCHandler.send_message
        mock_send_message.assert_called_with(message_type, data)


class TestWebSocketHandler(WebSocketHandler):
    def initialize(self, close_future, compression_options=None):
        self.close_future = close_future
        self.compression_options = compression_options

    def get_compression_options(self):
        return self.compression_options

    def on_close(self):
        super().on_close()
        self.close_future.set_result((self.close_code, self.close_reason))


class TestSocketHandler(TestWebSocketHandler, lib.SocketHandler):
    pass


class SocketHandlerTest(WebSocketBaseTestCase, TestCase):
    def setUp(self):
        super().setUp()
        self.player = BaseTestCase.create_players(1)[0]

    def send_message(self, data):

        string = json.dumps(data)
        websocket_connect(
            'ws://127.0.0.1:%d/' % self.get_http_port(),
            io_loop=self.io_loop,
            callback=self.stop,
        )
        ws = self.wait().result()
        ws.write_message(string)

    def get_app(self):
        self.close_future = Future()
        return Application(
            [('/', TestSocketHandler, dict(close_future=self.close_future)),]
        )

    @patch('airport.lib.SocketHandler.broadcast')
    def test_open(self, mock_broadcast):
        # given the logged in player
        player = self.player
        self.client.login(username=player.username, password='test')

        # when we connect to the websocket handler
        with patch('airport.lib.SocketHandler.get_current_user') as gcu:
            gcu.return_value = player
            websocket_connect(
                'ws://127.0.0.1:%d/' % self.get_http_port(),
                io_loop=self.io_loop,
                callback=self.stop,
            )
            ws = self.wait().result()

        # then the connection is added to the list of clients
        self.assertEqual(len(TestSocketHandler.clients), 1)

        # then a broadcast message is sent to all players
        client = TestSocketHandler.clients[0]
        mock_broadcast.assert_called_with(
            'new_connection', player.username, exclude=[client]
        )

        # and when we close the connection
        ws.read_message(self.stop)
        self.close_future.add_done_callback(lambda f: self.stop())
        ws.close()
        self.wait()

        # then a the client gets removed
        self.assertEqual(len(TestSocketHandler.clients), 0)

    @gen_test
    def test_message(self):
        # given the player with a websocket connection
        player = self.player
        user = player.user

        with patch('airport.lib.SocketHandler.get_current_user') as gcu:
            gcu.return_value = user
            ws = yield self.ws_connect('/')

        # when we call send_message()
        result = TestSocketHandler.message(user, 'player_message', 'test')

        # then the message gets sent to the one connection
        self.assertEqual(result, 1)

        # and we can read the message
        result = yield ws.read_message()
        result = json.loads(result)
        expected = {'type': 'player_message', 'data': 'test'}
        self.assertEqual(result, expected)

        yield self.close(ws)

    @gen_test
    def test_broadcast(self):
        # given the player with a websocket connection
        player = self.player

        with patch('airport.lib.SocketHandler.get_current_user') as gcu:
            gcu.return_value = player.user
            ws = yield self.ws_connect('/')

        # when we call broadcast()
        result = TestSocketHandler.broadcast('player_message', 'test')

        # then we can read the message
        result = yield ws.read_message()
        result = json.loads(result)
        expected = {'type': 'player_message', 'data': 'test'}
        self.assertEqual(result, expected)

        yield self.close(ws)

    @gen_test
    def test_games_info(self):
        # given the player
        player = self.player

        # and a game the player is hosting
        game = BaseTestCase.create_game(player)

        # when we call game_info()
        with patch('airport.lib.SocketHandler.get_current_user') as gcu:
            gcu.return_value = player.user
            ws = yield self.ws_connect('/')
        TestSocketHandler.games_info()

        # then the client is sent game infos
        result = yield ws.read_message()
        result = json.loads(result)
        expected = {
            'data': {
                'current_game': game.pk,
                'current_state': 'hosting',
                'finished_current': False,
                'games': [
                    {
                        'airports': game.airports.count(),
                        'created': 'now',
                        'goals': game.goals.count(),
                        'host': player.username,
                        'id': game.pk,
                        'players': game.players.distinct().count(),
                        'status': 'New',
                        'url': '%s?id=%s'
                        % (reverse('airport.views.games_join'), game.pk),
                    }
                ],
            },
            'type': 'games_info',
        }

        self.assertEqual(result, expected)
        yield self.close(ws)

    def test_get_current_user(self):
        # given the logged in client
        self.client.login(username=self.player.username, password='test')

        request = Mock()
        request.cookies = self.client.cookies

        # and the SocketHandler
        handler = lib.SocketHandler(self.get_app(), request)

        # when we call get_current_user()
        user = handler.get_current_user()

        # then we get the user
        self.assertEqual(user, self.player.user)

    def test_get_current_user_no_session(self):
        # given the user who hasn't logged in
        self.client.get('/')

        request = Mock()
        request.cookies = self.client.cookies

        # and the SocketHandler
        handler = lib.SocketHandler(self.get_app(), request)

        # when we call get_current_user()
        user = handler.get_current_user()

        # then we get None
        self.assertEqual(user, None)

    def test_get_current_user_bad_session(self):
        # given the session with a bad sessionid
        self.client.get('/')

        request = Mock()
        request.cookies = self.client.cookies
        request.cookies['sessionid'] = 'bogus'

        # and the SocketHandler
        handler = lib.SocketHandler(self.get_app(), request)

        # when we call get_current_user()
        user = handler.get_current_user()

        # then we get None
        self.assertEqual(user, None)


class TestIPCHandler(TestWebSocketHandler, lib.IPCHandler):
    pass


class IPCHandlerTest(WebSocketBaseTestCase, TestCase):
    def setUp(self):
        super().setUp()
        self.player = BaseTestCase.create_players(1)[0]

    def _send_message(self, message_type, data):

        message = {'type': message_type, 'key': settings.SECRET_KEY, 'data': data}
        message = json.dumps(message)
        websocket_connect(
            'ws://127.0.0.1:%d/ipc' % self.get_http_port(),
            io_loop=self.io_loop,
            callback=self.stop,
        )
        ws = self.wait().result()
        ws.write_message(message)
        ws.close()

    def message(self, message_type, data):
        s = {'type': message_type, 'key': settings.SECRET_KEY, 'data': data}
        s = json.dumps(s)
        return s

    def get_app(self):
        self.close_future = Future()
        return Application(
            [('/ipc', TestIPCHandler, dict(close_future=self.close_future)),]
        )

    @patch('airport.lib.logger')
    @gen_test
    def test_on_message_bad_key(self, mock_logger):
        # given the message containing a bad key
        data = {'type': 'info', 'data': 'hack hack hack', 'key': 'bogus key'}
        datas = json.dumps(data)

        # when we send the message to the ipc handler
        ws = yield self.ws_connect('/ipc')
        ws.write_message(datas)

        yield self.close(ws)

        # then a message is logged
        expected = call.critical('Someone is trying to hack me!', extra=data)
        self.assertTrue(expected in mock_logger.mock_calls, mock_logger.mock_calls)

    @patch('airport.lib.SocketHandler.message')
    @gen_test
    def test_handle_info(self, mock_ws_msg):

        # given the info message
        message = self.message(
            'info',
            {'player': self.player.username, 'data': {'this': 'is', 'a': 'test'}},
        )

        # when the message is send to ipc
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it (attempts to) send a message to the user
        mock_ws_msg.assert_called_with(
            self.player.user,
            'info',
            {'player': self.player.username, 'data': {'this': 'is', 'a': 'test'}},
        )

    @patch('airport.lib.SocketHandler.message')
    @gen_test
    def test_handle_start_game(self, mock_ws_msg):
        # given the game
        game = BaseTestCase.create_game(self.player)

        # when we send a start_game_thead message to ipc
        message = self.message('start_game', game.pk)
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it sends a message to all the players
        self.assertEqual(
            mock_ws_msg.call_count, game.players.filter(ai_player=False).count()
        )

    @patch('airport.lib.SocketHandler.games_info')
    @gen_test
    def test_handle_game_created(self, mock_ws_games_info):
        # given the game
        game = BaseTestCase.create_game(self.player)

        # when we send a game_created message to the ipc
        message = self.message('game_created', game.pk)
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it sends a games_info() message to all the players
        mock_ws_games_info.assert_called()

    @patch('airport.lib.SocketHandler.games_info')
    @gen_test
    def test_handle_game_ended(self, mock_ws_games_info):
        # given the game
        game = BaseTestCase.create_game(self.player)
        game.begin()
        game.end()

        # when we send a game_ended message to the ipc
        message = self.message('game_ended', game.pk)
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it sends a games_info() message to all the players
        mock_ws_games_info.assert_called()

    @patch('airport.lib.SocketHandler.games_info')
    @gen_test
    def test_handle_game_paused(self, mock_ws_games_info):
        # given the game
        game = BaseTestCase.create_game(self.player)
        game.begin()
        game.pause()

        # when we send a game_paused message to the ipc
        message = self.message('game_paused', game.pk)
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it sends a games_info() message to all the players
        mock_ws_games_info.assert_called()

    @patch('airport.lib.SocketHandler.games_info')
    @gen_test
    def test_handle_player_joined_game(self, mock_ws_games_info):
        # when we send a player_joined_game message to the ipc
        message = self.message('player_joined_game', {})
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it sends a games_info() message to all the players
        mock_ws_games_info.assert_called()

    @patch('airport.lib.SocketHandler.games_info')
    @gen_test
    def test_handle_player_left_game(self, mock_ws_games_info):
        # given the player and game
        player = self.player
        game = BaseTestCase.create_game(player)

        # when we send a player_left_game message to the ipc
        message = self.message('player_left_game', (player.pk, game.pk))
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it sends a games_info() message to all the players
        mock_ws_games_info.assert_called()

    @patch('airport.lib.SocketHandler.broadcast')
    @gen_test
    def test_handle_broadcast(self, mock_broadcast):
        # when we send a wall message to the ipc
        message = self.message('wall', 'Hello world!')
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it sends a broadcast() message to all the players
        mock_broadcast.assert_called_with('wall', 'Hello world!')

    @patch('airport.monkeywrench.MonkeyWrenchFactory.create')
    @gen_test
    def test_handle_throw_wrench(self, mock_mwf):
        # given the game
        game = BaseTestCase.create_game(self.player)
        game.begin()

        # when we send a throw_wrench message to the ipc
        message = self.message('throw_wrench', game.pk)
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it raises a monkey wrench in the game
        mock_mwf.assert_called_with(game)
        throw = call().throw()
        self.assertTrue(throw in mock_mwf.mock_calls)

    @patch('airport.lib.os.kill')
    @patch('airport.lib.sys.exit')
    @gen_test
    def test_handle_shutdown(self, mock_exit, mock_kill):
        # when we send a shutdown message to the ipc
        message = self.message('shutdown', {})
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it attempts to kill itself
        self.assertTrue(mock_kill.called)
        self.assertTrue(mock_exit.called)

    @patch('airport.lib.SocketHandler.message')
    @gen_test
    def test_handle_player_message(self, mock_ws_msg):
        # given the player
        player = self.player

        # when we call player_message to send a message to the player
        message = self.message(
            'player_message', {'player': player.username, 'message': 'Hello player!'}
        )
        ws = yield self.ws_connect('/ipc')
        ws.write_message(message)
        yield self.close(ws)

        # then it attempt to send the message to the player via the websocket
        # handler
        mock_ws_msg.assert_called_with(player.user, 'message', 'Hello player!')


class GameServerTest(BaseTestCase):
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
        ach = db.Achievement.objects.get(player=self.player, game=self.game)
        ach = ach.fulfill(now)
        self.assertTrue(self.player.finished(self.game))

        # when we join a new game
        game = db.Game.objects.create_game(
            ai_player=True, host=self.player, goals=1, airports=10
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
        game = db.Game.objects.get(pk=self.game.pk)
        self.assertEqual(game.state, game.GAME_OVER)

    @patch('airport.lib.send_message')
    def test_pause_game(self, send_message):
        """We can pause a game"""
        # Given the players and games
        game1 = self.game
        user2 = User.objects.create_user(username='test2', password='test')
        player2 = db.Player.objects.create(user=user2)
        game2 = db.Game.objects.create_game(host=player2, goals=3, airports=15)
        lib.start_game(game1)
        lib.start_game(game2)

        # When we pause a game from the managment command
        management.call_command('gameserver', pause=game1.pk)

        # Then that game is paused
        # (re-fetch)
        game1 = db.Game.objects.get(pk=game1.pk)
        game2 = db.Game.objects.get(pk=game2.pk)

        self.assertEqual(game1.state, game1.PAUSED)
        self.assertEqual(game2.state, game2.IN_PROGRESS)

        # Calling with "--resume" resumes the game
        management.call_command('gameserver', resume=game1.pk)
        # (re-fetch)
        game1 = db.Game.objects.get(pk=game1.pk)
        game2 = db.Game.objects.get(pk=game2.pk)
        self.assertEqual(game1.state, game1.IN_PROGRESS)
        self.assertEqual(game2.state, game2.IN_PROGRESS)

        # Calling --pause with id=0 pauses all active games
        management.call_command('gameserver', pause=0)

        for game in db.Game.objects.exclude(state__gt=0):
            self.assertEqual(game.state, game.PAUSED)

        # Calling --resume with id=0 resumes all active games
        management.call_command('gameserver', resume=0)

        for game in db.Game.objects.exclude(state__gt=0):
            self.assertEqual(game.state, game.IN_PROGRESS)

    @patch('airport.lib.send_message')
    def test_create_game(self, send_message):
        """Create a game through the management command"""
        self.game.end()
        games = db.Game.objects.filter(host=self.player, state=db.Game.IN_PROGRESS)
        self.assertFalse(games.exists())
        management.call_command('gameserver', creategame=self.player.username)

        games = db.Game.objects.filter(host=self.player, state=db.Game.IN_PROGRESS)
        self.assertTrue(games.exists())

    @patch('airport.lib.send_message')
    def test_create_game_with_args(self, send_message):
        """Create a game using --create user:airports:goals"""
        self.game.end()
        num_airports = 19
        arg = '{0}:{1}'.format(self.player.username, num_airports)
        management.call_command('gameserver', creategame=arg)
        games = db.Game.objects.filter(host=self.player, state=db.Game.IN_PROGRESS)
        self.assertTrue(games.exists())
        game = games[0]
        self.assertEqual(game.host, self.player)
        self.assertEqual(game.airports.count(), num_airports)
        self.assertEqual(game.goals.count(), 3)  # default

        # now try it specifying the goals too
        game.end()
        num_airports = 91
        num_goals = 14
        arg = '{0}:{1}:{2}'.format(self.player.username, num_airports, num_goals,)
        management.call_command('gameserver', creategame=arg)
        games = db.Game.objects.filter(host=self.player, state=db.Game.IN_PROGRESS)
        self.assertTrue(games.exists())
        game = games[0]
        self.assertEqual(game.host, self.player)
        self.assertEqual(game.airports.count(), num_airports)
        self.assertEqual(game.goals.count(), num_goals)
