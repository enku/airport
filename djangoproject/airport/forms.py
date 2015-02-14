from django import forms

from airport import models


class CreateGameForm(forms.Form):
    goals = forms.IntegerField(min_value=1, max_value=5, initial=1)
    airports = forms.IntegerField(min_value=1, initial=1)
    ai_player = forms.ChoiceField(
        initial='Yes',
        choices=(('Yes', 'Yes'), ('No', 'No')),
    )
    start_city = forms.CharField(required=False)

    def clean_ai_player(self):
        ai_player = self.cleaned_data['ai_player']
        if ai_player == 'Yes':
            return True

        if ai_player == 'No':
            return False

        raise forms.ValidationError('Must be "Yes" or "No"')

    def clean_airports(self):
        num_airports = models.AirportMaster.objects.count()
        airports = self.cleaned_data['airports']
        if airports > num_airports:
            txt = 'No more than {0} airports allowed.'
            txt = txt.format(num_airports)
            raise forms.ValidationError(txt)
        return airports
