from tempfile import NamedTemporaryFile

from django.shortcuts import render
from django.views.generic import TemplateView,FormView
from django.shortcuts import get_object_or_404
from django.urls import reverse

from terp.models import Story
from terp.forms import StoryForm

class HomeView(TemplateView):
    template_name = 'terp/home.html'

    def get_context_data(self):
        return {'stories': Story.objects.all().order_by('title')}

class LoadStoryView(FormView):
    template_name = 'terp/load_story.html'
    form_class = StoryForm

    def form_valid(self, form):
        # Stage file
        uploaded_file = self.request.FILES['story_file']

        f = NamedTemporaryFile(delete=False)
        for chunk in uploaded_file.chunks():
            f.write(chunk)
        f.seek(0)
        
        story,created = Story.objects.get_or_create_from_path(f.name,uploaded_file.name)
    
        return super(LoadStoryView,self).form_valid(form)

    def get_success_url(self):
        return reverse('home')


class PlayStoryView(TemplateView):
    template_name = 'terp/load_story.html'

    def get_context_data(self,story_id):
        story = get_object_or_404(Story, pk=story_id)
        return {'story': story}