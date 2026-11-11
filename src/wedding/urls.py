from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    # Main pages
    path('', views.homepage_view, name='homepage'),
    path('gifts/', RedirectView.as_view(url='https://www.milirose.com/liste-cadeaux-1443749.html'), name='gift_list'),
    path('rsvp/thanks/', views.rsvp_thanks_view, name='rsvp_thanks'),
    path('rsvp/', views.rsvp_lookup_view, name='rsvp_lookup'),
    path('rsvp/<str:invitation_code>/', views.rsvp_view, name='rsvp'),
]
