from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

# --- 1. THE IMPORT FIX ---
# We now import 'Item' and 'Variant', and have removed 'Service'
from .models import (
    Holding, Deal, Transaction, Profile, Asset, 
    Category, Item, Variant
)


class HoldingForm(forms.ModelForm):
    investor = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = Holding
        fields = ['investor', 'shares_held']
        widgets = {
            'shares_held': forms.NumberInput(attrs={
                'class': 'form-control', 
                'id': 'id_shares_held'
            }),
        }


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            'asset', 'title', 
            'target_raise_amount', 'total_shares_offered', 
            'launch_date', 'is_active'
        ]
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'target_raise_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_shares_offered': forms.NumberInput(attrs={'class': 'form-control'}),
            'launch_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_date', 'transaction_type', 'description', 'amount']
        widgets = {
            'transaction_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'transaction_type': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'E.g., "Monthly Rent for Nov" or "Rooftop Repair"'}
            ),
            'amount': forms.NumberInput(
                attrs={'class': 'form-control', 'placeholder': 'Use a negative number for expenses, e.g., -15000'}
            ),
        }


class SalesEntryForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_date', 'description', 'amount']
        widgets = {
            'transaction_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2, 
                         'placeholder': 'E.g., "Guest booking #123" or "3x Haircut service"'}
            ),
            'amount': forms.NumberInput(
                attrs={'class': 'form-control', 'placeholder': 'Enter a positive sales amount, e.g., 5000'}
            ),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError("Sales amount must be a positive number.")
        return amount


class UserRegistrationForm(forms.ModelForm):
    username = forms.CharField(
        label='Username', 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        label='First Name', 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label='Last Name', 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label='Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=Profile.ROLE_CHOICES, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assigned_asset = forms.ModelChoiceField(
        queryset=Asset.objects.all(), 
        required=False, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'password', 'role', 'assigned_asset']

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        if not self.request_user:
            return
        user_profile = self.request_user.profile
        
        if user_profile.role == 'MANAGER':
            if user_profile.assigned_asset:
                self.fields['assigned_asset'].queryset = Asset.objects.filter(
                    pk=user_profile.assigned_asset.pk
                )
                self.fields['assigned_asset'].initial = user_profile.assigned_asset
                self.fields['assigned_asset'].disabled = True
            self.fields['role'].choices = [('CASHIER', 'Cashier')]
            self.fields['role'].initial = 'CASHIER'
        
        elif user_profile.role == 'OWNER':
            self.fields['role'].choices = [
                ('MANAGER', 'Manager'),
                ('CASHIER', 'Cashier')
            ]
            self.fields['assigned_asset'].queryset = Asset.objects.all()

    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name']
        )
        Profile.objects.create(
            user=user,
            role=self.cleaned_data['role'],
            assigned_asset=self.cleaned_data.get('assigned_asset')
        )
        return user


# --- 2. THE 'ServiceForm' FIX ---
# We replace 'ServiceForm' with 'ItemForm' and 'VariantForm'
# deals/forms.py

# deals/forms.py

class ItemForm(forms.ModelForm):
    """
    A form for Owners/Managers to create or edit a base Item.
    """
    class Meta:
        model = Item
        fields = ['category', 'name', 'description']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# You can DELETE the old 'VariantForm' class, we don't need it.

class VariantForm(forms.ModelForm):
    """
    A form for adding a new Variant (e.g., "Small", "Large") to an Item.
    """
    class Meta:
        model = Variant
        fields = ['name', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "e.g., 'Small' or '60 Mins'"}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class UserUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=Profile.ROLE_CHOICES, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assigned_asset = forms.ModelChoiceField(
        queryset=Asset.objects.all(), 
        required=False, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['role'].initial = self.instance.profile.role
            self.fields['assigned_asset'].initial = self.instance.profile.assigned_asset
        
        if self.request_user and self.request_user.profile.role == 'MANAGER':
            manager_asset = self.request_user.profile.assigned_asset
            if manager_asset:
                self.fields['assigned_asset'].queryset = Asset.objects.filter(pk=manager_asset.pk)
                self.fields['assigned_asset'].disabled = True
            self.fields['role'].choices = [('CASHIER', 'Cashier')]
            self.fields['role'].disabled = True
        elif self.request_user and self.request_user.profile.role == 'OWNER':
            self.fields['role'].choices = [
                ('MANAGER', 'Manager'),
                ('CASHIER', 'Cashier')
            ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.profile.role = self.cleaned_data['role']
        user.profile.assigned_asset = self.cleaned_data.get('assigned_asset')
        if commit:
            user.save()
            user.profile.save()
        return user

    
# --- 3. THE 'SalesReportForm' FIX ---
# We removed the duplicate definition
class SalesReportForm(forms.Form):
    """
    A simple form for filtering sales transactions by date.
    """
    date_from = forms.DateField(
        required=False, 
        initial=timezone.now().date(), 
        widget=forms.DateInput(attrs={
            'class': 'form-control', 
            'type': 'date', 
            'id': 'date_from'
        })
    )
    date_to = forms.DateField(
        required=False, 
        initial=timezone.now().date(), 
        widget=forms.DateInput(attrs={
            'class': 'form-control', 
            'type': 'date', 
            'id': 'date_to'
        })
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }