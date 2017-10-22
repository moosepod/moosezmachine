from django.shortcuts import render
from django.views.generic import TemplateView

from terp.models import Story

class HomeView(TemplateView):
    template_name = 'terp/home.html'

    def get_context_data(self,**kwargs):
        return {'stories': Story.objects.all().order_by('title')}