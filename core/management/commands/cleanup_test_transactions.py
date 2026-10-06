from django.core.management.base import BaseCommand
from django.db import transaction

from transactions.models import Transaction


class Command(BaseCommand):
    help = "Remove all test/ demo transactions to keep only real transaction data"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation',
        )

    def handle(self, *args, **options):
        self.stdout.write("Cleaning up test transactions...")

        # Count existing transactions
        total_transactions = Transaction.objects.count()
        self.stdout.write(f"Found {total_transactions} transactions in database")

        if total_transactions == 0:
            self.stdout.write(self.style.WARNING("No transactions to clean up"))
            return

        # Ask for confirmation unless --force is used
        if not options['force']:
            self.stdout.write(self.style.WARNING("This will DELETE ALL transactions from the database."))
            self.stdout.write("Type 'yes' to confirm, or anything else to cancel:")

            confirmation = input("> ")

            if confirmation.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Operation cancelled"))
                return

        # Delete all transactions
        with transaction.atomic():
            deleted_count = Transaction.objects.all().delete()[0]

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} transactions"))
        self.stdout.write("Only real transactions will be created from now on")
        self.stdout.write("Transaction statistics will sync with real data only")