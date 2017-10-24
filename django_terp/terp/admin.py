from django.contrib import admin

from terp.models import StorySession,Story,StoryState

admin.site.register(Story)
admin.site.register(StorySession)
admin.site.register(StoryState)