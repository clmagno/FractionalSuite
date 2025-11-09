import csv
import datetime
from decimal import Decimal
from io import BytesIO

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User 
from django.db.models import Sum, F
from django.forms import inlineformset_factory
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import CreateView, UpdateView
from xhtml2pdf import pisa

# --- 1. Corrected Model Imports ---
from .models import (
    Deal, Asset, Transaction, SaleItem, Category, 
    Holding, Item, Variant, Sale, Profile
)
# --- 2. Corrected Form Imports ---
from .forms import (
    HoldingForm, DealForm, TransactionForm, 
    UserRegistrationForm, ItemForm, VariantForm, UserUpdateForm, 
    SalesReportForm, CategoryForm
)


@login_required
def dashboard_redirect_view(request):
    """
    This is the main "hub" after login. It checks the user's
    role and sends them to the correct page.
    """
    profile = request.user.profile
    
    if profile.role == 'CASHIER':
        if profile.assigned_asset:
            # Find an active deal for this asset
            active_deal = profile.assigned_asset.deals.filter(is_active=True).first()
            if active_deal:
                return redirect('pos-view', pk=active_deal.pk)
            else:
                messages.error(request, 'Your assigned asset has no active deal. Please contact your manager.')
                return redirect('logout')
        else:
            messages.error(request, 'You are not assigned to an asset. Please contact your manager.')
            return redirect('logout')

    if profile.role == 'MANAGER':
        return redirect('manager-dashboard')

    if profile.role == 'OWNER':
        return redirect('deal-list')

    messages.error(request, 'Your user role is not configured.')
    return redirect('logout')


@login_required
def deal_list(request):
    """
    This view is now OWNER-ONLY.
    It fetches and displays all active, launched deals.
    """
    profile = request.user.profile
    today = timezone.now().date()
    
    if profile.role == 'OWNER':
        active_deals = Deal.objects.filter(
            is_active=True,
            launch_date__lte=today
        ).select_related('asset')
    else:
        return redirect('dashboard-redirect')

    context = {
        'deals': active_deals,
    }
    return render(request, 'deals/deal_list.html', context)

@login_required
def deal_detail(request, pk):
    """
    This view displays deal data and handles the 'Add Holding' form.
    """
    today = timezone.now().date()
    deal = get_object_or_404(
        Deal, 
        pk=pk, 
        is_active=True, 
        launch_date__lte=today
    )
    if request.method == 'POST':
        form = HoldingForm(request.POST)
        if form.is_valid():
            investor = form.cleaned_data['investor']
            new_shares = form.cleaned_data['shares_held']
            new_cost_basis = new_shares * deal.price_per_share
            
            holding, created = Holding.objects.get_or_create(
                investor=investor,
                deal=deal,
                defaults={
                    'shares_held': new_shares,
                    'total_cost_basis': new_cost_basis
                }
            )
            
            if not created:
                holding.shares_held += new_shares
                holding.total_cost_basis += new_cost_basis
                holding.save()
                messages.success(request, f"Successfully added {new_shares} more shares to {investor.username}'s holding.")
            else:
                messages.success(request, f"Successfully added {new_shares} shares for new investor {investor.username}.")

            return redirect('deal-detail', pk=deal.pk)
    else:
        form = HoldingForm()

    transactions = deal.transactions.all().order_by('-transaction_date')
    valuations = deal.valuations.all()
    holdings = deal.holdings.all().select_related('investor')
    current_share_value = deal.calculate_current_share_value()

    context = {
        'deal': deal,
        'transactions': transactions,
        'valuations': valuations,
        'current_share_value': current_share_value,
        'holdings': holdings,
        'form': form, 
    }
    return render(request, 'deals/deal_detail.html', context)


class DealCreateView(LoginRequiredMixin, CreateView):
    model = Deal
    form_class = DealForm
    template_name = 'deals/deal_form.html'  
    success_url = reverse_lazy('deal-list') 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New Deal'
        context['cancel_url'] = reverse_lazy('deal-list')
        return context


class DealUpdateView(LoginRequiredMixin, UpdateView):
    model = Deal
    form_class = DealForm
    template_name = 'deals/deal_form.html'
    success_url = reverse_lazy('deal-list') 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit Deal'
        return context

    
@login_required
def deal_transaction_view(request, pk):
    """
    A dedicated page to add and view all transactions for a single deal.
    """
    deal = get_object_or_404(Deal, pk=pk)
    
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.deal = deal
            transaction.save()
            return redirect('deal-transactions', pk=deal.pk)
    else:
        form = TransactionForm()

    transactions = deal.transactions.all().order_by('-transaction_date')
    
    context = {
        'deal': deal,
        'form': form,
        'transactions': transactions,
    }
    return render(request, 'deals/deal_transactions.html', context)


@login_required
def user_registration_view(request):
    """
    A view for Owners and Managers to register new users.
    """
    if request.user.profile.role == 'CASHIER':
        return redirect('dashboard-redirect')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created successfully!')
            return redirect('deal-list')
    else:
        form = UserRegistrationForm(request_user=request.user)

    context = {
        'form': form,
        'page_title': 'Register New User'
    }
    return render(request, 'deals/user_registration.html', context)


@login_required
def manager_dashboard_view(request):
    """
    Shows the 'square buttons' dashboard for a Manager.
    """
    profile = request.user.profile
    if profile.role != 'MANAGER':
        return redirect('dashboard-redirect')
    
    asset = profile.assigned_asset
    if not asset:
        messages.error(request, "You are not assigned to an asset. Please contact the owner.")
        return redirect('logout')

    context = {
        'asset': asset
    }
    return render(request, 'deals/manager_dashboard.html', context)


@login_required
def manage_users_view(request):
    """
    A dedicated page for a Manager to view, deactivate,
    and reactivate the Cashiers assigned to their asset.
    """
    profile = request.user.profile

    if profile.role != 'MANAGER' or not profile.assigned_asset:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('dashboard-redirect')
    
    manager_asset = profile.assigned_asset

    if request.method == 'POST':
        user_pk = request.POST.get('user_pk')
        if user_pk:
            try:
                user_to_toggle = User.objects.get(pk=user_pk)
                if (user_to_toggle.profile.role == 'CASHIER' and 
                    user_to_toggle.profile.assigned_asset == manager_asset):
                    
                    user_to_toggle.is_active = not user_to_toggle.is_active
                    user_to_toggle.save()
                    
                    if user_to_toggle.is_active:
                        messages.success(request, f"User '{user_to_toggle.username}' has been activated.")
                    else:
                        messages.success(request, f"User '{user_to_toggle.username}' has been deactivated.")
                else:
                    messages.error(request, "You do not have permission to modify this user.")
            except User.DoesNotExist:
                messages.error(request, "User not found.")
        
        return redirect('manage-users')

    cashiers = User.objects.filter(
        profile__role='CASHIER',
        profile__assigned_asset=manager_asset
    ).order_by('username')

    context = {
        'asset': manager_asset,
        'cashiers': cashiers,
    }
    return render(request, 'deals/manage_users.html', context)


class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'deals/user_update.html'
    success_url = reverse_lazy('manage-users')

    def test_func(self):
        request_profile = self.request.user.profile
        user_to_edit = self.get_object()

        if request_profile.role == 'OWNER':
            return True 

        if request_profile.role == 'MANAGER':
            return (
                user_to_edit.profile.role == 'CASHIER' and
                user_to_edit.profile.assigned_asset == request_profile.assigned_asset
            )
        return False

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit User: {self.object.username}"
        return context


@login_required
def sales_report_view(request):
    """
    Shows a filterable sales report for a Manager's
    assigned asset, with PDF and CSV download.
    """
    profile = request.user.profile

    # --- 1. Permission Check ---
    if profile.role != 'MANAGER' or not profile.assigned_asset:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('dashboard-redirect')
    
    manager_asset = profile.assigned_asset

    # --- 2. Get Form Data ---
    form = SalesReportForm(request.GET or None)
    
    # Get dates from form, or default to today
    today = datetime.date.today()
    date_from_str = request.GET.get('date_from', today.strftime('%Y-%m-%d'))
    date_to_str = request.GET.get('date_to', today.strftime('%Y-%m-%d'))

    # --- 3. Get Base Queryset for DETAILED items ---
    sale_items_query = SaleItem.objects.filter(
        sale__deal__asset=manager_asset
    ).select_related(
        'sale', 'sale__cashier', 'variant', 'variant__item', 'variant__item__category'
    )

    if date_from_str:
        sale_items_query = sale_items_query.filter(sale__created_at__date__gte=date_from_str)
    if date_to_str:
        sale_items_query = sale_items_query.filter(sale__created_at__date__lte=date_to_str)
        
    sale_items = sale_items_query.order_by('sale__created_at')

    # --- 4. Calculate Totals (VAT-Inclusive) ---
    total_sales = sale_items.aggregate(total=Sum(F('price_at_sale') * F('quantity')))['total'] or Decimal('0.00')
    vatable_sales = total_sales / Decimal('1.12')
    vat_amount = total_sales - vatable_sales

    # --- 5. Handle Downloads ---
    
    # --- PDF Download ---
    if request.GET.get('download') == 'pdf':
        context = {
            'asset': manager_asset,
            'sale_items': sale_items,
            'total_sales': total_sales,
            'vatable_sales': vatable_sales,
            'vat_amount': vat_amount,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'today': today.strftime('%Y-%m-%d'),
        }
        html_string = render_to_string('deals/sales_report_pdf.html', context)
        result = BytesIO()
        pdf = pisa.pisaDocument(
            BytesIO(html_string.encode("UTF-8")),
            result
        )
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="sales_report_{manager_asset.name}.pdf"'
            return response
        else:
            messages.error(request, "There was an error generating the PDF.")
            return redirect('sales-report')

    # --- CSV Download ---
    if request.GET.get('download') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sales_report_DETAILED_{manager_asset.name}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Sale ID', 'Date', 'Time', 'Cashier', 'Customer', 
            'Category', 'Item', 'Variant', 'Qty', 'Unit Price', 'Line Total'
        ])
        for item in sale_items:
            writer.writerow([
                item.sale.pk,
                item.sale.created_at.strftime('%Y-%m-%d'),
                item.sale.created_at.strftime('%H:%M'),
                item.sale.cashier.username,
                item.sale.customer_name,
                item.variant.item.category.name,
                item.variant.item.name,
                item.variant.name,
                item.quantity,
                item.price_at_sale,
                item.total_price
            ])
        return response

    # --- 6. Render the HTML page (for web view) ---
    web_transactions = Transaction.objects.filter(
        deal__asset=manager_asset,
        transaction_type='INCOME',
        transaction_date__date__gte=date_from_str,
        transaction_date__date__lte=date_to_str
    ).order_by('-transaction_date')
    
    context = {
        'asset': manager_asset,
        'form': form,
        'transactions': web_transactions,
        'total_sales': total_sales,
    }
    return render(request, 'deals/sales_report.html', context)


# --- MANAGE ITEMS VIEW ---
@login_required
def manage_items_view(request, asset_pk):
    """
    A dedicated page for an Owner or assigned Manager to
    add and view all Items for a single asset.
    """
    asset = get_object_or_404(Asset, pk=asset_pk)
    profile = request.user.profile

    is_owner = profile.role == 'OWNER'
    is_assigned_manager = (
        profile.role == 'MANAGER' and 
        profile.assigned_asset == asset
    )
    if not (is_owner or is_assigned_manager):
        return HttpResponseForbidden("You do not have permission to access this page.")

    category_queryset = Category.objects.filter(asset=asset)

    if request.method == 'POST':
        form = ItemForm(request.POST) 
        form.fields['category'].queryset = category_queryset
        
        if form.is_valid():
            item = form.save() 
            messages.success(request, f"Item '{item.name}' created successfully.")
            return redirect('manage-items', asset_pk=asset.pk) 
    else:
        form = ItemForm() 
        form.fields['category'].queryset = category_queryset

    items = Item.objects.filter(category__asset=asset).order_by('category__name', 'name')

    context = {
        'asset': asset,
        'form': form,
        'items': items, 
    }
    return render(request, 'deals/manage_items.html', context) 


# --- ITEM/VARIANT UPDATE VIEW ---
@login_required
def manage_item_variants_view(request, pk):
    """
    This is the new "Edit Item" page.
    It handles editing the Item AND all its Variants on one page.
    """
    item = get_object_or_404(Item, pk=pk)
    asset = item.asset
    profile = request.user.profile

    is_owner = profile.role == 'OWNER'
    is_assigned_manager = (
        profile.role == 'MANAGER' and 
        profile.assigned_asset == asset
    )
    if not (is_owner or is_assigned_manager):
        return HttpResponseForbidden("You do not have permission to access this page.")

    VariantFormSet = inlineformset_factory(
        Item,
        Variant,
        form=VariantForm, # Use our custom form
        fields=('name', 'price'),
        extra=1,
        can_delete=True,
        widgets={
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    )

    if request.method == 'POST':
        item_form = ItemForm(request.POST, instance=item)
        variant_formset = VariantFormSet(request.POST, instance=item)
        
        if item_form.is_valid() and variant_formset.is_valid():
            item_form.save()
            variant_formset.save()
            messages.success(request, f"Successfully updated '{item.name}'.")
            return redirect('manage-items', asset_pk=asset.pk)
    else:
        item_form = ItemForm(instance=item)
        variant_formset = VariantFormSet(instance=item)

    context = {
        'item': item,
        'item_form': item_form,
        'variant_formset': variant_formset,
        'page_title': f"Edit Item: {item.name}"
    }
    return render(request, 'deals/item_form_edit.html', context)


# --- POS VIEW ---
@login_required
def pos_view(request, pk):
    """
    A dedicated POS portal for a Cashier with category filters
    and a variant selection modal.
    """
    profile = request.user.profile
    deal = get_object_or_404(Deal, pk=pk, is_active=True)
    asset = deal.asset

    is_cashier = profile.role == 'CASHIER' and profile.assigned_asset == asset
    is_manager_or_owner = (
        profile.role in ['MANAGER', 'OWNER'] and
        (profile.role == 'OWNER' or profile.assigned_asset == asset)
    )
    if not (is_cashier or is_manager_or_owner):
        messages.error(request, "You do not have permission to access this page.")
        return redirect('dashboard-redirect')

    categories = Category.objects.filter(asset=asset).order_by('name')
    active_category_id = request.GET.get('category')
    
    if active_category_id:
        items = Item.objects.filter(category__id=active_category_id).prefetch_related('variants')
        active_category_id = int(active_category_id)
    else:
        items = Item.objects.filter(category__asset=asset).prefetch_related('variants').order_by('name')

    cart = request.session.get('cart', {})
    
    if request.method == 'POST':
        
        if 'add_to_cart' in request.POST:
            variant_id = request.POST.get('variant_id')
            variant = get_object_or_404(Variant, pk=variant_id)
            
            if str(variant_id) in cart: # Use string keys
                cart[str(variant_id)]['quantity'] += 1
            else:
                cart[str(variant_id)] = {
                    'id': variant.id,
                    'name': f"{variant.item.name} ({variant.name})",
                    'price': float(variant.price),
                    'quantity': 1
                }
            messages.success(request, f"Added '{cart[str(variant_id)]['name']}' to cart.")

        elif 'remove_from_cart' in request.POST:
            variant_id = request.POST.get('variant_id')
            if str(variant_id) in cart: # Use string keys
                item = cart.pop(str(variant_id))
                messages.warning(request, f"Removed '{item['name']}' from cart.")

        elif 'checkout' in request.POST:
            customer_name = request.POST.get('customer_name', 'Walk-in')
            if not cart:
                messages.error(request, "Cannot check out an empty cart.")
            else:
                sale = Sale.objects.create(
                    deal=deal, 
                    cashier=request.user, 
                    customer_name=customer_name
                )
                
                for variant_id, item in cart.items():
                    SaleItem.objects.create(
                        sale=sale,
                        variant=get_object_or_404(Variant, pk=variant_id),
                        price_at_sale=item['price'],
                        quantity=item['quantity']
                    )
                
                sale.finalize_and_create_transaction()
                cart = {} 
                request.session['cart'] = cart
                messages.success(request, "Sale finalized successfully.")
                return redirect('sale-receipt', pk=sale.pk)

        request.session['cart'] = cart
        redirect_url = f"{reverse('pos-view', kwargs={'pk': pk})}"
        if active_category_id:
            redirect_url += f"?category={active_category_id}"
        return redirect(redirect_url)
    
    cart_items = []
    cart_total = 0
    
    for item in cart.values():
        line_total = item['price'] * item['quantity']
        item['line_total'] = line_total
        cart_total += line_total
        cart_items.append(item)
    
    context = {
        'deal': deal,
        'asset': asset,
        'items': items,
        'categories': categories,
        'active_category_id': active_category_id,
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'deals/pos_terminal.html', context)

# --- CATEGORY MANAGEMENT VIEWS ---
@login_required
def manage_categories_view(request, asset_pk):
    """
    A dedicated page for an Owner or assigned Manager to
    add, edit, and view all categories for a single asset.
    """
    asset = get_object_or_404(Asset, pk=asset_pk)
    profile = request.user.profile

    is_owner = profile.role == 'OWNER'
    is_assigned_manager = (
        profile.role == 'MANAGER' and 
        profile.assigned_asset == asset
    )
    if not (is_owner or is_assigned_manager):
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.asset = asset
            category.save()
            messages.success(request, f"Category '{category.name}' created successfully.")
            return redirect('manage-categories', asset_pk=asset.pk)
    else:
        form = CategoryForm()

    categories = Category.objects.filter(asset=asset).order_by('name')

    context = {
        'asset': asset,
        'form': form,
        'categories': categories,
    }
    return render(request, 'deals/manage_categories.html', context)


class CategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    View to edit an existing Category.
    """
    model = Category
    form_class = CategoryForm
    template_name = 'deals/category_form_edit.html'
    
    def test_func(self):
        profile = self.request.user.profile
        category = self.get_object()
        
        is_owner = profile.role == 'OWNER'
        is_assigned_manager = (
            profile.role == 'MANAGER' and
            profile.assigned_asset == category.asset
        )
        return is_owner or is_assigned_manager

    def get_success_url(self):
        return reverse_lazy('manage-categories', kwargs={'asset_pk': self.object.asset.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit Category: {self.object.name}"
        return context


# --- SALE RECEIPT VIEW ---
@login_required
def sale_receipt_view(request, pk):
    """
    Displays a printable receipt for a completed sale.
    """
    sale = get_object_or_404(Sale, pk=pk)
    
    profile = request.user.profile
    asset = sale.deal.asset
    
    is_cashier = (profile.role == 'CASHIER' and request.user == sale.cashier)
    is_manager = (profile.role == 'MANAGER' and profile.assigned_asset == asset)
    is_owner = (profile.role == 'OWNER')
    
    if not (is_cashier or is_manager or is_owner):
        return HttpResponseForbidden("You do not have permission to view this receipt.")
        
    total_amount = sale.total_amount
    vatable_sales = total_amount / Decimal('1.12')
    vat_amount = total_amount - vatable_sales
    
    context = {
        'sale': sale,
        'asset': asset,
        'deal': sale.deal,
        'sale_items': sale.items.all(),
        'vatable_sales': vatable_sales,
        'vat_amount': vat_amount,
    }
    return render(request, 'deals/sale_receipt.html', context)