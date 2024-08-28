"""
This module contains Django forms used in the pyvcloud_project application.

Available Forms:
- OrgvdcEdit: Form for editing OrgVdcs.
- UploadISOForm: Form for uploading an ISO file.

"""

from django import forms
from django.forms import HiddenInput, ModelForm, NumberInput, Select
from pyvcloud_project.models import OrgVdcs


class OrgvdcEdit(ModelForm):
    """
    Form for editing OrgVdcs.
    """

    class Meta:  # pylint: disable=too-few-public-methods
        """ Options for the ModelForm. """
        model = OrgVdcs
        fields = ('name', 'cpu_limit', 'memory_limit', 'running_tb_limit',
                  'stored_tb_limit', 'mig_ra_obj', 'org_vdc_id')
        widgets = {
            'name': HiddenInput(attrs={'id': 'name',
                                       'name': 'name',
                                       'required': True}),
            'cpu_limit': NumberInput(attrs={'id': 'cpu_limit',
                                            'name': 'cpu_limit',
                                            'required': True}),
            'memory_limit': NumberInput(attrs={'id': 'memory_limit',
                                               'name': 'memory_limit',
                                               'required': True}),
            'running_tb_limit': NumberInput(attrs={'id': 'running_tb_limit',
                                                   'name': 'running_tb_limit',
                                                   'required': True}),
            'stored_tb_limit': NumberInput(attrs={'id': 'stored_tb_limit',
                                                  'name': 'stored_tb_limit',
                                                  'required': True}),
            'mig_ra_obj': Select(attrs={'id': 'mig_ra_obj',
                                        'name': 'mig_ra_obj',
                                        'required': True}),
            'org_vdc_id': HiddenInput(attrs={'id': 'org_vdc_id', 'required': True})
        }
        labels = {
            'mig_ra_obj': 'Ra',
            'stored_tb_limit': 'Total vApps Quota',
            'running_tb_limit': 'Running vApps Quota',
            'cpu_limit': 'Running CPUs Quota',
            'memory_limit': 'Running Memory Quota (GB)'
        }


class UploadISOForm(forms.Form):
    """
    Form for uploading ISO file.
    """

    file = forms.FileField(allow_empty_file=False,
                           label='Upload ISO File', required=True)
