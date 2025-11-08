from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# --- 1. THIS IS THE FIX ---
# We now import Category, Item, and Variant
# We have REMOVED 'Service'
from .models import (
    Asset, Deal, Holding, Valuation, Transaction, 
    Profile, Category, Item, Variant, Sale, SaleItem
)

# --- 2. User & Profile Admin (No change) ---
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fields = ('role', 'assigned_asset')

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_role')
    @admin.display(description='Role')
    def get_role(self, obj):
        return getattr(obj, 'profile', None) # Use getattr for safety
    
    def get_inlines(self, request, obj=None):
        if obj:
            return (ProfileInline,)
        return ()

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# --- 3. Asset Admin (No change) ---
class DealInline(admin.TabularInline):
    model = Deal
    extra = 0
class CategoryInline(admin.TabularInline):
    model = Category
    extra = 0
    
@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'asset_type', 'location')
    inlines = [CategoryInline, DealInline]


# --- 4. 'ServiceAdmin' is now 'ItemAdmin' ---
class VariantInline(admin.TabularInline):
    model = Variant
    extra = 1

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'asset_name')
    list_filter = ('category__asset', 'category')
    search_fields = ('name',)
    inlines = [VariantInline]

    @admin.display(description='Asset')
    def asset_name(self, obj):
        return obj.category.asset.name


# --- 5. Deal & Sale Admin (Updates) ---
class ValuationInline(admin.StackedInline):
    model = Valuation
    extra = 0
class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0

# 'SaleItemInline' now uses 'variant'
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('variant', 'price_at_sale')
    can_delete = False

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('title', 'asset', 'is_active', 'price_per_share', 'display_current_share_value')
    list_filter = ('is_active', 'asset')
    inlines = [ValuationInline, TransactionInline]
    readonly_fields = ('price_per_share',)
    
    @admin.display(description='Current NAV/Share')
    def display_current_share_value(self, obj):
        return obj.calculate_current_share_value()
    
    class Media:
        js = ("js/deal_admin.js",)

@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('investor', 'deal', 'shares_held', 'total_cost_basis')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'deal', 'cashier', 'customer_name', 'total_amount', 'created_at')
    inlines = [SaleItemInline]