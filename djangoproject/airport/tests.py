import datetime
import random

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
        self.assertRaises(models.SchedulingError, flight.cancel, now)

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
        flight1.depart_time = datetime.datetime(2011, 11, 18, 7, 0)
        flight1.save()
        self.assertEqual(airport.next_flight_to(city, now), flight2)

