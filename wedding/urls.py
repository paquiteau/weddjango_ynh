from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.homepage_view, name='homepage'),
    path('gifts/', views.gift_list_view, name='gift_list'),
    
    # RSVP process
    path('rsvp/<str:invitation_code>/', views.rsvp_view, name='rsvp'),
    path('rsvp/thanks/', views.rsvp_thanks_view, name='rsvp_thanks'),
]
