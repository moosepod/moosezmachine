from django.conf.urls import url

from terp import views

urlpatterns = [
    url(r'^$', views.HomeView.as_view()),
]
