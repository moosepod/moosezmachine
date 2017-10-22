from django import forms

class StoryForm(forms.Form):
    story_file = forms.FileField()
