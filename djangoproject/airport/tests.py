import datetime
import random

from django.contrib.auth.models import User
from django.test import TestCase

import models

AP_TUPLE = (('RDU', 'Raleigh/Durham International', 'Raleigh'),
        ('DFW', 'Dallas/Fort Worth International', 'Dallas'),
        ('PHX', 'Phoenix Sky Harbor', 'Phoenix'),
        ('LAX', 'Los Angeles International', 'Los Angeles'),
        ('SFO', 'San Francisco International', 'San Francisco'),
        ('MIA', 'Miami Internationa', 'Miami'),
        ('ORD', 'Chicago O\'Hare', 'Chicago'),
        ('MDW', 'Chicago Midway', 'Chicago'),
        ('BWI', 'Baltimore/Washington International', 'Baltimore'),
        ('BOS', 'Boston Logan', 'Boston'),
        ('LAS', 'McCarran International', 'Las Vegas'),
        ('EWR', 'Newark Liberty International', 'Newark'),
        ('JFK', 'John F. Kennedy International', 'New York'),
        ('LGA', 'LaGuardia International', 'New York'))

class AirportTest(TestCase):
    """Test Airport Model"""

    def setUp(self):
        "setup"

        # create some airports
        for t in AP_TUPLE:
            city = models.City.objects.get_or_create(name=t[2])[0]
            models.Airport.objects.create(
                    name=t[1],
                    code=t[0],
                    city=city)

        airports = models.Airport.objects.all()
        for airport in airports:
            for i in range(5):
                destination = random.choice(airports)
                if destination.city != airport.city:
                    airport.destinations.add(destination)
            airport.clean()
            airport.save()


    def test_next_flights(self):
        """Test that we can see next flights"""
        airport = random.choice(models.Airport.objects.all())
        now = datetime.datetime(2011, 11, 17, 11, 0)
        time1 = datetime.datetime(2011, 11, 17, 11, 30)
        dest1 = random.choice(airport.destinations.all())
        time2 = datetime.datetime(2911, 11, 17, 12, 0)
        dest2 = random.choice(airport.destinations.all())

        flight1 = models.Flight.objects.create(
                origin = airport,
                destination = dest1,
                depart_time = time1,
                flight_time = 200)

        flight2 = models.Flight.objects.create(
                origin = airport,
                destination = dest2,
                depart_time = time2,
                flight_time = 200)

        next_flights = airport.next_flights(now)
        self.assertEqual(next_flights.count(), 2)
        next_flights = airport.next_flights(time1)
        self.assertEqual(next_flights.count(), 1)
        next_flights = airport.next_flights(time2)
        self.assertEqual(next_flights.count(), 0)

class FlightTest(TestCase):
    """Test the Flight Model"""

    def setUp(self):
        "setup"

        # create some airports
        for t in AP_TUPLE:
            city = models.City.objects.get_or_create(name=t[2])[0]
            models.Airport.objects.create(
                    name=t[1],
                    code=t[0],
                    city=city)

        airports = models.Airport.objects.all()
        for airport in airports:
            for i in range(5):
                destination = random.choice(airports)
                if destination.city != airport.city:
                    airport.destinations.add(destination)
            airport.clean()
            airport.save()

    def test_in_flight(self):
        """Test the in_flight() and cancel() methods"""
        airports = models.Airport.objects.all()
        airport = random.choice(airports)
        destination = random.choice(airport.destinations.all())
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
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
        self.assertRaises(models.FlightAlreadyDeparted, flight.cancel, now)

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
        destination = random.choice(airport.destinations.all())
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
                origin = airport,
                destination = destination,
                depart_time = depart_time,
                flight_time = flight_time)

        self.assertEqual(flight.destination_city, destination.city)
        self.assertEqual(flight.origin_city, airport.city)

    def test_next_flight_to(self):
        """Test the next_flight_to() method"""
        now = datetime.datetime(2011, 11, 17, 11, 0)
        airport = random.choice(models.Airport.objects.all())
        city = random.choice(models.City.objects.exclude(
            id=airport.city.id))

        dest = models.Airport.objects.filter(city=city)[0]
        time1 = datetime.datetime(2011, 11, 17, 11, 30)
        flight1 = models.Flight.objects.create(
                origin = airport,
                destination = dest,
                depart_time = time1,
                flight_time = 200)

        time2 = datetime.datetime(2011, 11, 17, 12, 0)
        flight2 = models.Flight.objects.create(
                origin = airport,
                destination = dest,
                depart_time = time2,
                flight_time = 200)

        city2 = random.choice(models.City.objects.exclude(
            id=airport.city.id).exclude(id=city.id))
        dest2 = models.Airport.objects.filter(city=city2)[0]
        flight3 = models.Flight.objects.create(
                origin = airport,
                destination = dest2,
                depart_time = time2,
                flight_time = 200)

        self.assertEqual(airport.next_flight_to(city, now), flight1)
        airport2 = models.Airport.objects.filter(city=city)[0]
        self.assertEqual(airport.next_flight_to(airport2, now), flight1)
        self.assertEqual(airport.next_flight_to(city2, now), flight3)

        # delay flight1
        flight1.delay(datetime.timedelta(minutes=450), now)
        self.assertEqual(airport.next_flight_to(city, now), flight2)

    def test_create_flights(self):
        """test the create flights method"""
        airports = models.Airport.objects.all()
        airport = random.choice(airports)

        self.assertEqual(models.Flight.objects.all().count(), 0)

        now = datetime.datetime(2011, 11, 20, 6, 43)
        airport.create_flights(now)
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
        depart_time = datetime.datetime(2011, 11, 18, 4, 50)
        flight_time = 60

        flight = models.Flight.objects.create(
                origin = airport,
                destination = destination,
                depart_time = depart_time,
                flight_time = flight_time)

        d = flight.to_dict()
        self.assertEqual(type(d), dict)
        self.assertEqual(sorted(d.keys()), sorted([
            'number', 'depart_time', 'arrival_time', 'destination',
            'status']))
        self.assertEqual(d['status'], 'On time')

        flight.delay(datetime.timedelta(minutes=20),
                datetime.datetime(2011, 11, 18, 4, 0))
        d = flight.to_dict()
        self.assertEqual(d['status'], 'Delayed')

        flight.cancel()
        d = flight.to_dict()
        self.assertEqual(d['status'], 'Cancelled')

class UserProfileTest(TestCase):
    """Test the UserProfile model"""

    def setUp(self):
        """setup for UserProfileTest"""
        # create a user
        self.user = User.objects.create_user(username='test',
            email='test@test.com', password='test')
        self.up = models.UserProfile.objects.create(user=self.user)

        # create some airports
        for t in AP_TUPLE:
            city = models.City.objects.get_or_create(name=t[2])[0]
            models.Airport.objects.create(
                    name=t[1],
                    code=t[0],
                    city=city)

        airports = models.Airport.objects.all()
        for airport in airports:
            for i in range(5):
                destination = random.choice(airports)
                if destination.city != airport.city:
                    airport.destinations.add(destination)
            airport.clean()
            airport.save()

    def test_location(self):
        """Test the location() method"""
        now = datetime.datetime(2011, 11, 20, 7, 13)
        l = self.up.location(now)
        self.assertEqual(l, None)

        airport = random.choice(models.Airport.objects.all())
        airport.create_flights()
        flight = random.choice(airport.flights.all())

        self.up.airport = airport
        self.up.save()
        self.up.buy_ticket(flight, now)
        l = self.up.location(now)
        self.assertEqual(self.up.ticket, flight)
        self.assertEqual(l, airport)

        # Take off!, assert we are in flight
        l = self.up.location(flight.depart_time)
        self.assertEqual(l, flight)

        # when flight is delayed we are still in the air
        original_arrival = flight.arrival_time
        flight.delay(datetime.timedelta(minutes=20), now)
        l = self.up.location(original_arrival)
        self.assertEqual(l, flight)

        # now land
        now = flight.arrival_time + datetime.timedelta(minutes=1)
        l = self.up.location(now)
        self.assertEqual(l, flight.destination)

    def test_buy_ticket(self):
        """Test the buy_ticket() method"""
        now = datetime.datetime(2011, 11, 20, 7, 13)
        l = self.up.location(now)
        self.assertEqual(l, None)

        airport = random.choice(models.Airport.objects.all())
        airport.create_flights()
        flight = random.choice(airport.flights.all())

        # assert we can't buy the ticket (flight) if we're not at the airport
        self.assertRaises(models.FlightNotAtDepartingAirport,
                self.up.buy_ticket, flight, now)

        self.up.airport = airport
        self.up.save()

        # attempt to buy a flight while in flight
        self.up.buy_ticket(flight, now)
        now = flight.depart_time
        flight2 = random.choice(airport.flights.exclude(id=flight.id))
        self.assertRaises(models.FlightAlreadyDeparted, self.up.buy_ticket,
                flight2, now)

        # ok let's land
        now = flight.arrival_time + datetime.timedelta(minutes=1)
        l = self.up.location(now)

        # make sure we have flights
        l.create_flights(now)

        # lounge around for a while...
        now = now + datetime.timedelta(minutes=60)

        # find a flight that's already departed
        flight3 = random.choice(l.flights.filter(depart_time__lte=now))

        # try to buy it
        self.assertRaises(models.FlightAlreadyDeparted, self.up.buy_ticket,
                flight3, now)

