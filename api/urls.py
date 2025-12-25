from django.urls import path
from . import views

urlpatterns = [
    path("blogposts/", views.BlogPostListCreate.as_view(), name="blogpost-view-create"), #sunset
    path("blogposts/<int:pk>/", views.BlogPostRetrieveUpdateDestroy.as_view(), name="blogpost-retrieve-update-destroy"), #sunset
    path("blogposts/list/", views.BlogPostList.as_view(), name="blogpost-list"), #sunset
    path("doSomething/", views.DoSomethingView.as_view(), name="do-something"),
    path("processTradingViewSignal/", views.ProcessTradingViewSignal.as_view(), name="process-tradingview-signal"),
    path("callGeminiApi/", views.callGeminiApi.as_view(), name="call-gemini-api"), #sunset
    path("banditMessages/", views.BanditMessages.as_view(), name="bandit-messages"), #add authentication
]
