from django import forms

from . import models

class CreateStoryForm(forms.Form):
	story_file = forms.FileField()

	def clean_story_file(self):
		story_file = self.cleaned_data['story_file']
		self.filename = story_file._name
		if not self.filename.endswith('.z3') and not self.filename.endswith('.z5'):
			raise forms.ValidationError('Mooseterp only handles zcode files (ending in .z3 or .z5)')
		self.story_file_data = bytearray(story_file.read())
		story = models.Story(story_data=self.story_file_data)
		try:
			story.get_zmachine()
		except Exception as e:
			raise forms.ValidationError('This does not appear to be a valid story file. %s.' % e)
		return story_file

	def save(self, who):
		return models.Story.objects.create(title=self.filename,
			story_data=self.story_file_data,
			created_by=who)