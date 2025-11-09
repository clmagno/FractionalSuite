from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum

class Asset(models.Model):
    """
    Represents the actual, physical asset being invested in.
    E.g., "Sunlit Coast Resort", "Main St. Food Stall #3"
    """
    ASSET_TYPES = [
        ('REAL_ESTATE', 'Real Estate (Resort, Hotel, Airbnb)'),
        ('BUSINESS', 'Small Business (Parlor, Food Stall)'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=255)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPES)
    location = models.CharField(max_length=255, blank=True, help_text="Full business address")
    
    description = models.TextField(blank=True)
    tin_number = models.CharField(max_length=20, blank=True, null=True, help_text="e.g., 000-000-000-001")
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name
class Profile(models.Model):
    ROLE_CHOICES = (
        ('OWNER', 'Owner'),
        ('MANAGER', 'Manager'),
        ('CASHIER', 'Cashier'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='CASHIER')
    
    # This is the key to solving Concern #2
    # An Owner/Manager might not be assigned, so we allow null
    assigned_asset = models.ForeignKey(
        Asset, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="The asset this user is assigned to (e.g., for Cashiers)."
    )

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
class Category(models.Model):
    """
    Represents a POS category, like 'Nail Services', 'Add-ons', or 'Beverages'.
    This is managed by the Owner/Manager.
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    
    class Meta:
        verbose_name_plural = "Categories" # Fixes "Categorys" in admin

    def __str__(self):
        return f"{self.name} (for {self.asset.name})"
class Item(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    @property
    def asset(self):
        return self.category.asset

    def __str__(self):
        return self.name

# --- 2. ADD the new 'Variant' model ---
# This holds the specific options and prices (e.g., "Regular Polish", "Medium")
class Variant(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=100, help_text="e.g., 'Small', 'Medium', 'Regular', '1 hr'")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.item.name} ({self.name}) - ₱{self.price}"

# ... (Deal, Holding, Valuation, Transaction, Sale models are fine) ...


# 2. The Investment Deal (The "Offering")
class Deal(models.Model):
    """
    Represents the financial offering for a specific asset.
    An Asset can have multiple Deals over time (e.g., "2025 Initial Offering").
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="deals")
    title = models.CharField(max_length=255, help_text="e.g., '2025 Series A Fractional Offering'")
    
    # Deal Structure
    target_raise_amount = models.DecimalField(max_digits=15, decimal_places=2)
    total_shares_offered = models.PositiveIntegerField()
    
    
    # Status
    launch_date = models.DateField()
    is_active = models.BooleanField(default=False, help_text="Is this deal open for investment?")
    def calculate_current_share_value(self):
        """
        Calculates the current Net Asset Value (NAV) per share.
        
        Logic: (Latest Official Valuation + Net Cash Flow Since Valuation) / Total Shares
        """
        
        # 1. Get the latest official valuation
        latest_valuation = self.valuations.first() # We set ordering = ['-valuation_date']
        
        if not latest_valuation:
            # If no valuation, return the initial offering price
            return self.price_per_share

        latest_valuation_amount = latest_valuation.total_valuation
        latest_valuation_date = latest_valuation.valuation_date

        # 2. Calculate net cash flow (Income - Expense) since that valuation
        net_cash_flow = self.transactions.filter(
            transaction_date__gt=latest_valuation_date
        ).aggregate(
            total=Sum(
                models.Case(
                    models.When(transaction_type='INCOME', then='amount'),
                    models.When(transaction_type='EXPENSE', then=models.F('amount') * -1),
                    default=Decimal(0)
                )
            )
        )['total'] or Decimal(0)

        # 3. Calculate current NAV
        current_nav = latest_valuation_amount + net_cash_flow
        
        # 4. Calculate NAV per share
        if self.total_shares_offered == 0:
            return Decimal(0) # Avoid division by zero
            
        nav_per_share = current_nav / self.total_shares_offered
        
        return nav_per_share.quantize(Decimal('0.00'))
    def __str__(self):
        return self.title
    @property
    def price_per_share(self):
        """
        Calculates the price per share on the fly.
        """
        if self.total_shares_offered and self.target_raise_amount:
            price = self.target_raise_amount / Decimal(self.total_shares_offered)
            return price.quantize(Decimal('0.00'))
        return Decimal(0)
    def total_shares_sold(self):
        """
        Calculates the sum of all shares held by investors for this deal.
        """
        # This queries all related 'Holding' objects and sums their 'shares_held'
        result = self.holdings.aggregate(total=Sum('shares_held'))
        return result['total'] or 0
    @property
    def shares_available(self):
        """
        Calculates the remaining shares available for purchase.
        """
        return self.total_shares_offered - self.total_shares_sold()

    @property
    def percentage_sold(self):
        """
        Calculates the percentage of shares sold, for the progress bar.
        """
        if self.total_shares_offered == 0:
            return 0

        # We use float() to ensure we get a decimal for the percentage
        percent = (float(self.total_shares_sold()) / float(self.total_shares_offered)) * 100
        return round(percent, 2)

    

# 3. Investor Holdings (The "Ownership")
class Holding(models.Model):
    """
    Connects a User (Investor) to a Deal, showing how many shares they own.
    """
    investor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="holdings")
    deal = models.ForeignKey(Deal, on_delete=models.PROTECT, related_name="holdings")
    shares_held = models.PositiveIntegerField()
    
    # We record the price to track an investor's cost basis
    total_cost_basis = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        unique_together = ('investor', 'deal') # Each investor has one holding per deal

    def __str__(self):
        return f"{self.investor.username} - {self.shares_held} shares in {self.deal.title}"

# 4. Admin-Set Valuation (The "Dynamic Value")
class Valuation(models.Model):
    """
    Stores the official, admin-set valuation for a deal at a specific point in time.
    """
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="valuations")
    valuation_date = models.DateField()
    total_valuation = models.DecimalField(max_digits=15, decimal_places=2)
    valuation_method = models.CharField(max_length=255, help_text="e.g., 'Annual Appraisal', 'Admin Re-evaluation'")

    class Meta:
        ordering = ['-valuation_date'] # Always get the latest one first
        unique_together = ('deal', 'valuation_date')

    def __str__(self):
        return f"{self.deal.title} valued at {self.total_valuation} on {self.valuation_date}"
        
# 5. Asset/Deal Transactions (The "Cash Flow")
class Transaction(models.Model):
    """
    Tracks all cash flow for a Deal (e.g., rental income, maintenance costs).
    This is used to calculate performance *between* official valuations.
    """
    TRANSACTION_TYPES = [
        ('INCOME', 'Income (e.g., rent, sales)'),
        ('EXPENSE', 'Expense (e.g., maintenance, fees)'),
        ('DISTRIBUTION', 'Distribution (Payout to investors)'),
    ]
    
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="transactions")
    transaction_date = models.DateTimeField(default=timezone.now)
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2) # Positive for income, negative for expense
    description = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.transaction_type} for {self.deal.title}: {self.amount}"

class Sale(models.Model):
    """
    Represents a single 'receipt' or 'checkout event' at the POS.
    This groups multiple SaleItems and generates one Transaction.
    """
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="sales")
    cashier = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sales")
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Sale #{self.pk} by {self.cashier.username} on {self.created_at.strftime('%Y-%m-%d')}"

    def finalize_and_create_transaction(self):
        """
        Calculates the final total from all SaleItems and creates
        a single, corresponding INCOME Transaction.
        """
        # Calculate total from items
        total = 0
        for item in self.items.all():
            total += item.total_price
            
        self.total_amount = total
        self.save()
        
        # Create the one ledger entry
        Transaction.objects.create(
            deal=self.deal,
            transaction_type='INCOME',
            amount=self.total_amount,
            description=f"POS Sale #{self.pk} (Cashier: {self.cashier.username})",
            transaction_date=self.created_at
        )
        return self
        


class SaleItem(models.Model):
  """
  Represents a single line item on a Sale (receipt).
  e.g., "1 x Manicure"
  """
  sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
  variant = models.ForeignKey(Variant, on_delete=models.PROTECT)
  quantity = models.PositiveIntegerField(default=1)
  price_at_sale = models.DecimalField(max_digits=10, decimal_places=2) 
  
  @property
  def total_price(self):
    return self.quantity * self.price_at_sale
  def __str__(self):
    return f"{self.quantity} x {self.variant.item.name} ({self.variant.name}) for Sale #{self.sale.pk}"
