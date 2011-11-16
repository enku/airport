from django.db import models

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
