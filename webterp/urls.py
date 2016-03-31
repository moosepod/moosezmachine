from django.conf.urls import url
from django.contrib.auth.decorators import login_required, permission_required

from . import views

urlpatterns = [
    url(r'^$', login_required(views.StoryListView.as_view()), name='story_list'),
    url(r'^create/$', login_required(views.StoryCreateView.as_view()),name='story_create'),

]