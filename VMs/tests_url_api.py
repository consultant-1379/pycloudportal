from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import Client
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from django.conf import settings
from pyvcloud_project.models import SppUser


class VmsAPITestCase(APITestCase):
    settings.TEST = True

    @classmethod
    def setUpTestData(self):
        # Set up test data
        self.client = Client()
        # Vapp Name: newv
        self.vapp_vcd_id_powered_off = 'urn:vcloud:vapp:a84dc1d5-2b82-4eec-a32f-7e948a8de27f'
        # Vapp Name: abc789
        self.vapp_vcd_id_powered_on = 'urn:vcloud:vapp:788c3d1b-313c-4f57-8b35-b6a92ea429f2'
        # Vapp Name: abc456
        self.vapp_vcd_id_partially_powered_of = 'urn:vcloud:vapp:6603f7e6-9104-4480-831a-f5c24cbd9db3'
        # Catalog Vapp Name: 123abctemplate
        self.catalog_vapp_template_id = 'urn:vcloud:vdc:3608e6bd-102d-432a-998e-370c20795b33'

        self.username = 'testUser'
        self.password = 'testUserPassword'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
        )
        # Create SppUser object
        spp_user = SppUser.objects.create(
            user=self.user,
            ldap_groups='',
        )

    def setUp(self):
        # Log in the user
        self.logged_in = self.client.login(
            username=self.username,
            password=self.password
        )

    def test_get_vms_pass(self):
        """
        Test to get VM's of a Vapp
        """
        self.assertTrue(self.logged_in)
        url = reverse('Vms-api:get_vms',
                      kwargs={'vapp_vcd_id': self.vapp_vcd_id_powered_off})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_message = "VM's Retuned Successfully"
        response_data = response.json()

        self.assertIn('message', response_data)
        self.assertEqual(response_data['message'], expected_message)

        expected_vm_keys = ['name', 'status', 'number_of_cpus', 'memory_mb', 'committed_storage',
                            'provisioned_storage', 'vsphere_name', 'hostname', 'id']

        for vm in response_data.get('VM_Details', []):
            for key in expected_vm_keys:
                self.assertIn(key, vm)

    def test_get_vms_from_template_pass(self):
        """
        Test to get VM's of a template
        """
        self.assertTrue(self.logged_in)
        url = reverse('Vms-api:get_vms_from_template',
                      kwargs={'template_id': self.catalog_vapp_template_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_message = "VM's Retuned Successfully"
        response_data = response.json()

        self.assertIn('message', response_data)
        self.assertEqual(response_data['message'], expected_message)

        expected_vm_keys = ['name', 'status',
                            'number_of_cpus', 'memory_allocation']

        for vm_data in response_data.get('VM_Details', {}).values():
            for key in expected_vm_keys:
                self.assertIn(key, vm_data)
