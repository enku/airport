import json
from unittest.mock import patch

from django.core.urlresolvers import reverse

from airport import models
from airport.tests import BaseTestCase


class ViewTest(BaseTestCase):
    """Test the home view"""
    view = reverse('main')

    def setUp(self):
        self.player, self.player2 = self.create_players(2)


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
        send_message.assert_called_with('start_game', game.pk)


def decode_response(response):
    """Take a response object and return the json-decoded content"""
    assert response.status_code == 200
    assert response['content-type'] == 'application/json'
    content = response.content
    content = content.decode(response.charset)
    return json.loads(content)
