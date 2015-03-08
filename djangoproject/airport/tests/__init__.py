"""Unit tests for airport"""
from django.test import TestCase
from django.contrib.auth.models import User

from airport import models


# base test cases
class BaseTestCase(TestCase):

    """Base test case for tests

    Creates an player, self.player, and a game, self.game, with that player (and
    an AI player)
    """

    def setUp(self):
        # create user and game
        self.player = self.create_players(1)[0]

        # create a game
        self.game = self.create_game(host=self.player)

    @staticmethod
    def create_players(num_players):
        """create num_players  users and Player.objects, return a tuple of the
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

    @staticmethod
    def create_game(host, goals=1, airports=15):
        """Create a game hostedy by host"""

        return models.Game.objects.create_game(
            host=host, goals=goals, airports=airports)
