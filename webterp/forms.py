from django import forms

from . import models

class CreateStoryForm(forms.Form):
	title = forms.CharField()

	def save(self, who):
		return models.Story.objects.create(title=self.cleaned_data['title'],
			story_data='test',
			created_by=who)