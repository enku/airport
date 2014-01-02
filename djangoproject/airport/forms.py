from django import forms

from .models import AirportMaster


class CreateGameForm(forms.Form):
    goals = forms.IntegerField(min_value=1, max_value=5, initial=1)
    airports = forms.IntegerField(min_value=1, initial=1)
    ai_player = forms.BooleanField(required=False, initial=True)

    def clean_airports(self):
        num_airports = AirportMaster.objects.count()
        airports = self.cleaned_data['airports']
        if airports > num_airports:
            txt = 'No more than {0} airports allowed.'
            txt = txt.format(num_airports)
            raise forms.ValidationError(txt)
        return airports
