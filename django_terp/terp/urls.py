from django.conf.urls import url

from terp import views

urlpatterns = [
    url(r'^$', views.HomeView.as_view(),name='home'),
    url(r'^load/$', views.LoadStoryView.as_view(),name='load_story'),
    url(r'^start/(?P<story_id>[0-9])/$', views.StartStoryView.as_view(),name='start_story'),
    url(r'^restart/(?P<story_id>[0-9])/$', views.RestartStoryView.as_view(),name='restart_story'),
    url(r'^play/(?P<session_id>[0-9])/$', views.PlaySessionView.as_view(),name='play'),
]
