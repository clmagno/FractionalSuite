# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from deals import views as deal_views  # We need this for the redirect view

urlpatterns = [
    # 1. Admin site
    path('admin/', admin.site.urls),
    
    # 2. Main Login/Logout URLs
    path('', 
         auth_views.LoginView.as_view(
             template_name='registration/login.html',
             redirect_authenticated_user=True 
         ), 
         name='login'),
    
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # 3. Main Redirect Hub
    path('dashboard/', deal_views.dashboard_redirect_view, name='dashboard-redirect'),

    # 4. The ONE entry point for ALL other deal-related pages
    # This tells Django: "For any URL starting with 'app/',
    # go look in 'deals.urls' for the rest of the path."
    # We'll call our app 'app/' to make it clean.
    path('app/', include('deals.urls')),
]