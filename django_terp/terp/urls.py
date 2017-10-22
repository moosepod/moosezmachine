from django.conf.urls import url

from terp import views

urlpatterns = [
    url(r'^$', views.HomeView.as_view(),name='home'),
    url(r'^load/$', views.LoadStoryView.as_view(),name='load_story'),
    url(r'^play/(?P<story_id>[0-9])/$', views.PlayStoryView.as_view(),name='play_story'),
]
