from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import reverse

def custom_login_view(request, **kwargs):
    if request.user.is_authenticated:
        # Logic for logged-in users
        profile = request.user.profile
        if profile.role == 'CASHIER' and profile.assigned_asset:
            # Find the first active deal for this asset to send them to
            active_deal = profile.assigned_asset.deals.filter(is_active=True).first()
            if active_deal:
                return redirect('deal-sales-entry', pk=active_deal.pk)

        # Owners and Managers go to the main deal list
        return redirect('deal-list')

    # If not authenticated, just show the standard login page
    return auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=False # Our function handles this now
    )(request, **kwargs)