from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Sum
from deals.models import Asset, Transaction, Profile
from django.contrib.auth.models import User
import datetime

class Command(BaseCommand):
    help = 'Sends the end-of-day sales report to all Platform Owners and Investors.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Starting Daily Report Job ---'))
        
        today = timezone.now().date()
        
        # 1. Get the list of ALL Platform Owners (you) ONCE.
        # We use set() to make merging lists easy.
        owner_emails = set(User.objects.filter(
            profile__role='OWNER', 
            email__isnull=False,
            is_active=True
        ).values_list('email', flat=True))
        
        if owner_emails:
            self.stdout.write(f'Found {len(owner_emails)} Platform Owner(s): {", ".join(owner_emails)}')
        else:
            self.stdout.write(self.style.WARNING('No Platform Owners with emails found.'))

        # 2. Find all assets that had INCOME transactions today
        asset_ids_with_sales = Transaction.objects.filter(
            transaction_type='INCOME',
            transaction_date__date=today
        ).values_list('deal__asset_id', flat=True).distinct()

        assets_to_report = Asset.objects.filter(pk__in=asset_ids_with_sales)

        if not assets_to_report.exists():
            self.stdout.write('No assets had sales today. Exiting.')
            return
            
        self.stdout.write(f'Found {assets_to_report.count()} asset(s) with sales to report on.')

        # 3. Loop through each asset, build its recipient list, and send the email
        for asset in assets_to_report:
            self.stdout.write(f'Processing: {asset.name}')

            # 4. Get all transactions for THIS asset today
            transactions = Transaction.objects.filter(
                deal__asset=asset,
                transaction_type='INCOME',
                transaction_date__date=today
            )
            total_sales = transactions.aggregate(total=Sum('amount'))['total'] or 0.00
            
            self.stdout.write(f'  -> Found {transactions.count()} transactions totaling ₱{total_sales}.')

            # 5. Get all Investors (Holders) for THIS asset
            investor_emails = set(User.objects.filter(
                holdings__deal__asset=asset,
                email__isnull=False,
                is_active=True
            ).values_list('email', flat=True))
            
            if investor_emails:
                self.stdout.write(f'  -> Found {len(investor_emails)} investor(s) for this asset.')

            # 6. Combine the lists (set logic removes duplicates)
            recipient_list = list(owner_emails | investor_emails)
            
            if not recipient_list:
                self.stdout.write(self.style.WARNING(f'  -> SKIPPING: No recipients with emails found for this asset.'))
                continue

            self.stdout.write(f'  -> Preparing to email {len(recipient_list)} total recipient(s).')

            # 7. Render the HTML email template
            context = {
                'asset': asset,
                'transactions': transactions,
                'total_sales': total_sales,
                'date_from': today.strftime('%Y-%m-%d'),
                'date_to': today.strftime('%Y-%m-%d'),
            }
            html_body = render_to_string('deals/email/sales_report_email.html', context)
            
            # 8. Send the email
            send_mail(
                subject=f"Daily Sales Report for {asset.name} - {today}",
                message=f"Total Sales for {today} for {asset.name}: ₱{total_sales}", # Plain text fallback
                from_email="chris.ultd@gmail.com",  # <-- ADD THIS LINE. Django will use settings.DEFAULT_FROM_EMAIL
                recipient_list=recipient_list, # Send to the combined list
                html_message=html_body,
            )
            
            self.stdout.write(self.style.SUCCESS(f'  -> Email for {asset.name} sent!'))

        self.stdout.write(self.style.SUCCESS('--- Daily reports finished ---'))