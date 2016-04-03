import json

from django.views.generic.list import ListView
from django.views.generic.edit import FormView
from django.core.urlresolvers import reverse
from django.views.generic import TemplateView,View
from django.shortcuts import get_object_or_404
from django.http import JsonResponse

from zmachine.interpreter import Interpreter,Story,OutputStreams,InputStreams

from . import models
from . import forms

from webterp import BufferOutputStream,BufferInputStream

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

class StoryPlayView(TemplateView):
	template_name = 'webterp/story_play.html'

	def get_context_data(self,**kwargs):
		ctx = {}

		story = get_object_or_404(models.Story,id=self.kwargs['uuid'])
		story_instance,created = models.StoryInstance.objects.get_or_create(story=story,
			user=self.request.user,
			defaults={'game_data': story.story_data}
		)
		ctx['story'] = story

		return ctx

class StorySubmitTextView(View):
    def post(self,*args,**kwargs):
        story_instance = models.StoryInstance.objects.get(story__id=self.kwargs['uuid'],
        user=self.request.user)
        
        text = self.request.POST.get('text')
        context = {'score': '','room_name':'','output': ''}

        story = Story(bytearray(story_instance.game_data))
        main_output_stream = BufferOutputStream()
        main_input_stream = BufferInputStream(text)
        outputs = OutputStreams(main_output_stream,BufferOutputStream())
        inputs = InputStreams(main_input_stream,BufferInputStream(''))
        zmachine = Interpreter(story,outputs,inputs,None,None)
        zmachine.reset()
        zmachine.output_streams.set_screen_stream(main_output_stream)
        zmachine.input_streams.select_stream(0)

        try:
            counter=0
            while not main_input_stream.waiting_for_line:
                zmachine.step()
                counter+=1
            context['output'] = main_output_stream.text
            context['score'] = main_output_stream.score_text
            context['room_name'] = main_output_stream.room_name
            story_instance.game_data = zmachine.story.game_memory._raw_data
            story_instance.save()
        except Exception as e:
            context['output'] = 'Error: %s' % e


        return JsonResponse(
            context
        )

