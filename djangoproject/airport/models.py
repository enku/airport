# -*- encoding: utf-8 -*-
import datetime

from django.core.exceptions import ValidationError
from django.db import models

class SchedulingError(Exception):
    pass

class City(models.Model):
    """A City"""
    name = models.CharField(max_length=50)

    def __unicode__(self):
        return self.name


    class Meta:
        verbose_name_plural = 'cities'


class Airport(models.Model):
    """An Airport"""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=4)
    city = models.ForeignKey(City)
    destinations = models.ManyToManyField('self', null=True, blank=True)

    def __unicode__(self):
        return self.code

    __str__ = __unicode__

    def next_flights(self, now=None):
        """Return outgoing flights for airport, but not past flights"""
        now = now or datetime.datetime.now()

        return self.flights.filter(depart_time__gt=now)

    def clean(self):
        """validation"""
        # airport destinations can't be in the same city
        if self.destinations.filter(city=self.city).exists():
            raise ValidationError(
                u'Airport cannot have itself as a destination.')

    def next_flight_to(self, city, now=None):
        """Return the next flight to «city» or None"""
        now = now or datetime.datetime.now()
        if isinstance(city, Airport):
            city = city.city
        next_flights = self.next_flights(now).filter(
                destination__city=city)

        if next_flights.exists():
            return next_flights[0]
        return None


class Flight(models.Model):
    """A flight from one airport to another"""
    number = models.CharField(max_length=12)
    origin = models.ForeignKey(Airport, related_name='flights')
    destination = models.ForeignKey(Airport, related_name='+')
    depart_time = models.DateTimeField()
    flight_time = models.IntegerField()

    def __unicode__(self):
        return u'%s from %s to %s departing %s' % (self.number,
                self.origin.name, self.destination.name, self.depart_time)

    @property
    def destination_city(self):
        return self.destination.city

    @property
    def origin_city(self):
        return self.origin.city

    def in_flight(self, now=None):
        """Return true if flight is in the air"""
        now = now or datetime.datetime.now()
        if self.flight_time == -1:
            return False

        arrival_time = (self.depart_time +
            datetime.timedelta(minutes=self.flight_time))

        if self.depart_time <= now <= arrival_time:
            return True

        return False

    @property
    def cancelled(self):
        """Return True iff a flight is cancelled"""
        return self.flight_time == -1

    def cancel(self, now=None):
        """Cancel a flight. In-flight flights (obviously) can't be
        cancelled"""
        now = now or datetime.datetime.now()

        if not self.in_flight(now):
            self.flight_time = -1
            self.save()

        else:
            raise SchedulingError('In-progress flight cannot be cancelled')

    def clean(self, *args, **kwargs):
        """Validate the model"""

        # Origin can't also be desitination
        if self.origin == self.destination:
            raise ValidationError(u'Origin and destination cannot be the same')

        if self.origin.desitinations.filter(id=self.destination.id).exists():
            raise ValidationError(u'%s not accessible from %s' %
                    (self.destination.code, self.origin.code))

        #return super(Flight, self).save(*args, **kwargs)


    class Meta:
        ordering = ['depart_time']

