from tempfile import NamedTemporaryFile

from django.shortcuts import render
from django.views.generic import TemplateView,FormView,RedirectView
from django.shortcuts import get_object_or_404
from django.urls import reverse

from terp.models import StoryRecord,StorySession,get_default_user
from terp.forms import StoryForm

class HomeView(TemplateView):
    template_name = 'terp/home.html'

    def get_context_data(self):
        return {'stories': StoryRecord.objects.all().order_by('title')}

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
        
        story,created = StoryRecord.objects.get_or_create_from_path(f.name,uploaded_file.name)
    
        return super(LoadStoryView,self).form_valid(form)

    def get_success_url(self):
        return reverse('home')


class StartStoryView(RedirectView):
    def get_redirect_url(self,story_id):
        story = get_object_or_404(StoryRecord, pk=story_id)

        session = story.get_or_start_session(get_default_user())

        return reverse('play',kwargs={'session_id': session.id})

class PlaySessionView(TemplateView):
    template_name = 'terp/play_story.html'

    def get_context_data(self,session_id):
        session = get_object_or_404(StorySession, pk=session_id)

        state = session.get_current_state()
        command = self.request.GET.get('command')
        if command:
            state = state.generate_next_state(command=command)

        return {'session': session,
                'state': state}
