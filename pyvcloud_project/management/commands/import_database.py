import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
import logging

class Command(BaseCommand):
    def handle(self, *args, **options):
        try:
            # Run Import jobs in sequence
            self.run_job('import_pvdc')
            self.run_job('import_organisations')
            self.run_job('import_orgvdc')
            self.run_job('import_catalogs')
            self.run_job('import_vapps')
            self.run_job('import_vms')
            self.run_job('import_vapp_networks')
            self.run_job('import_vm_storage_from_vsphere')
            self.stdout.write(self.style.SUCCESS('All Jobs are completed successfully'))

        except CommandError as e:
            self.stdout.write(self.style.ERROR(f'CommandError: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An unexpected error occurred: {str(e)}'))

    def run_job(self, job_name):
        self.stdout.write(f'Starting job: {job_name}')
        call_command(job_name)
        self.stdout.write(f'Finished job: {job_name}')
