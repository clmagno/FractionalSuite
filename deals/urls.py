# deals/urls.py
from django.urls import path
from . import views
from .views import (
    DealCreateView, DealUpdateView, UserUpdateView, 
    CategoryUpdateView, manage_item_variants_view
)

# All these URLs will be prefixed with /app/
urlpatterns = [
    # /app/
    path('', views.deal_list, name='deal-list'), 
    
    # --- Manager URLs ---
    # /app/manager/
    path('manager/', views.manager_dashboard_view, name='manager-dashboard'),
    # /app/manager/users/
    path('manager/users/', views.manage_users_view, name='manage-users'),
    # /app/manager/users/3/edit/
    path('manager/users/<int:pk>/edit/', UserUpdateView.as_view(), name='user-edit'),
    # /app/manager/reports/
    path('manager/reports/', views.sales_report_view, name='sales-report'),
    
    # --- User Registration ---
    # /app/register/
    path('register/', views.user_registration_view, name='user-register'),
    
    # --- Deal URLs ---
    # /app/create/
    path('create/', DealCreateView.as_view(), name='deal-create'),
    # /app/1/
    path('<int:pk>/', views.deal_detail, name='deal-detail'), 
    # /app/1/edit/
    path('<int:pk>/edit/', DealUpdateView.as_view(), name='deal-edit'), 
    # /app/1/transactions/
    path('<int:pk>/transactions/', views.deal_transaction_view, name='deal-transactions'),
    
    # --- POS URL ---
    # /app/1/pos/
    path('<int:pk>/pos/', views.pos_view, name='pos-view'),
    
    # --- Item & Category URLs ---
    # /app/asset/1/items/
    path('asset/<int:asset_pk>/items/', 
         views.manage_items_view, 
         name='manage-items'),
         
    # /app/items/1/edit/
    path('items/<int:pk>/edit/', 
         views.manage_item_variants_view, 
         name='item-edit'),
         
    # /app/asset/1/categories/
    path('asset/<int:asset_pk>/categories/', 
         views.manage_categories_view, 
         name='manage-categories'),
         
    # /app/categories/1/edit/
    path('categories/<int:pk>/edit/', 
         CategoryUpdateView.as_view(), 
         name='category-edit'),
]