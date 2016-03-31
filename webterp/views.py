from django.views.generic.list import ListView
from django.views.generic.edit import FormView
from django.core.urlresolvers import reverse

from . import models
from . import forms

class StoryListView(ListView):
    model = models.Story

class StoryCreateView(FormView):
	form_class = forms.CreateStoryForm
	template_name = 'webterp/story_form.html'

	def get_success_url(self):
		return reverse('story_list')

	def form_valid(self,form):
		form.save(self.request.user)
		return super(StoryCreateView,self).form_valid(form)
