import datetime
from unittest.mock import patch

from airport import lib, models, monkeywrench
from airport.tests import BaseTestCase


################################################################################
# MonkeyWrenches                                                               #
################################################################################
class MonkeyWrenchTestBase(BaseTestCase):
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
        cancelled = models.Flight.objects.filter(game=self.game, state='Cancelled')
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
            depart_time__gt=self.now, state='Delayed', game=self.game
        )
        airport = delayed_flights[0].origin
        airport_flights = models.Flight.objects.filter(
            depart_time__gt=self.now, game=self.game, origin=airport
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
            depart_time__gt=self.now, state='Cancelled', game=self.game
        )
        airport = delayed_flights[0].origin
        airport_flights = models.Flight.objects.filter(
            depart_time__gt=self.now, game=self.game, origin=airport
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
            game=self.game, depart_time__gt=self.now, full=True
        )
        self.assertEqual(flights.count(), 1)


class TSAMonkeyWrenchTest(MonkeyWrenchTestBase):
    """TSA MonkeyWrench"""

    def test_throw(self):
        # Given the monkeywrench
        mw = monkeywrench.TSA(self.game, self.now)
        mw.minutes_before_departure = 60

        # and the flight taking off within 60 minutes
        flight = models.Flight.objects.filter(
            game=self.game, origin=self.game.start_airport,
        )[0]
        flight.depart_time = self.now + datetime.timedelta(minutes=30)
        flight.arrival_time = self.now + datetime.timedelta(minutes=90)
        flight.save()

        # when a player purchases the flight
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
            (
                'Someone reported you as suspicious and you have been removed'
                ' from the plane.'
            ),
        )


class TailWindMonkeyWrenchTest(BaseTestCase):
    """HeadWind wrench."""

    @patch('airport.lib.send_message')
    def test_TailWind(self, send_message):
        # let's make sure at least one flight is in the air
        self.game.begin()
        now = lib.take_turn(self.game, throw_wrench=False)
        airport = self.game.start_airport
        flights_out = airport.next_flights(now, future_only=True, auto_create=False)

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
