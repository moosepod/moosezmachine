import json
from tempfile import NamedTemporaryFile

from django.shortcuts import render
from django.views.generic import TemplateView,FormView,RedirectView,View
from django.shortcuts import get_object_or_404,render
from django.http import HttpResponse
from django.urls import reverse

from terp.models import StoryRecord,StorySession,get_default_user,StoryState
from terp.forms import StoryForm

# How many moves back to show when loading the page
# from history/scratch
HISTORY_BUFFER_SIZE=4


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

class RestartStoryView(RedirectView):
    def get_redirect_url(self,story_id):
        story = get_object_or_404(StoryRecord, pk=story_id)

        session = story.get_or_start_session(get_default_user())

        # Clear old states
        session.storystate_set.all().delete()

        return reverse('play',kwargs={'session_id': session.id})

class PlaySessionView(TemplateView):
    template_name = 'terp/play_story.html'

    def get_context_data(self,session_id):
        session = get_object_or_404(StorySession, pk=session_id)

        history_id = self.request.GET.get('history_id')
        command = self.request.GET.get('command',None)

        state = session.get_current_state()

        return {'session': session,
                'state': state}

class PlaySessionHistoryView(TemplateView):
    template_name = 'terp/play_session.html'

    def get_context_data(self,session_id):
        session = get_object_or_404(StorySession, pk=session_id)

        return {'session': session,
                'history': StoryState.objects.all().order_by('-move')}

class PlaySessionInitialView(TemplateView):
    template_name = 'terp/play_command.html'

    def get_context_data(self,session_id):
        session = get_object_or_404(StorySession, pk=session_id)
        history_id = self.request.GET.get('history_id')

        if history_id:
            state = StoryState.objects.get(pk=history_id,session=session)
        else:
            state = session.get_current_state()

        start_move = max(state.move - HISTORY_BUFFER_SIZE,0)
        history = StoryState.objects.filter(session=session,move__gt=start_move,move__lte=state.move)

        return {'session': session,
                'history': history,
                'state': state}

class PlaySessionCommandView(View):
    def post(self,request, session_id):
        session = get_object_or_404(StorySession, pk=session_id)
        command = self.request.POST.get('command',None)

        state = session.get_current_state()
        if command:
            state = state.generate_next_state(command=command)

        return HttpResponse(json.dumps({'move': state.move,
                           'room_name': state.room_name,
                           'score': state.score,
                           'state_id': state.id,
                           'command': state.command,
                           'text': state.text}))
