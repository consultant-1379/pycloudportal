from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from django.test import TestCase, Client
from django.contrib.auth.models import User
from pyvcloud_project.models import SppUser
from pyvcloud_project.utils import pyvcloud_utils as utils
from django.conf import settings
import time


class VappPageApiTests(TestCase):
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
        # OrgVdc Name: Oceans
        self.org_vdc_id_oceans = 'urn:vcloud:vdc:7185dbd0-7c49-47b8-a9f3-ffa47315c5dd'

        self.client = Client()
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
        self.logged_in = self.client.login(
            username=self.username,
            password=self.password
        )
        # Get the Redis instance
        self.redis_instance = utils.get_redis()
        #  Default Value set to False
        self.vapp_added_to_redis = False

    def get_redis_cache(self, vapp_id):
        # Get the Redis value
        self.cache_value = self.redis_instance.exists(vapp_id)

    def manipulate_redis_cache(self, vapp_cache_key, add_to_cache, remove_from_cache):
        # Remove from cache if already exists
        if remove_from_cache:
            self.redis_instance.delete(vapp_cache_key)
            time.sleep(0.5)  # Add a 500ms delay here

        # Add the vApp back to the Redis cache
        if add_to_cache:
            # Set default value if self.cache_value is None
            self.cache_value = self.cache_value or b''
            self.redis_instance.set(vapp_cache_key, self.cache_value)
            time.sleep(0.5)  # Add a 500ms delay here

    def test_get_vapps_pass(self):
        """
        Test getting vApps
        """
        self.assertTrue(self.logged_in)
        response = self.client.get(
            reverse('Vapps-api:get_vapps', kwargs={'org_vdc_id': self.org_vdc_id_oceans}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_vapps_invalid_orgvdc(self):
        """
        Test getting vApps when invalid orgvdc passed
        """
        self.assertTrue(self.logged_in)
        self.org_vdc_id_oceans = 'invalid_org_vcd_id'
        response = self.client.get(
            reverse('Vapps-api:get_vapps', kwargs={'org_vdc_id': self.org_vdc_id_oceans}))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = "Error b'OrgVDC with ID: invalid_org_vcd_id not found'"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

    def test_get_vapp_status_pass(self):
        """
        Test getting vApp status when not in redis queue
        """
        self.assertTrue(self.logged_in)
        response = self.client.get(reverse(
            'Vapps-api:get_vapp_status', args=[self.vapp_vcd_id_powered_off, self.org_vdc_id_oceans]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_vapp_from_template_pass(self):
        """
        Test creating a vApp from a template when not in redis queue
        """
        self.assertTrue(self.logged_in)
        query_params = {
            'vapp_name': 'test_vapp_name',
            'power_state': 'on',
            'vapp_template_id': 'urn:vcloud:vapp:3608e6bd-102d-432a-998e-370c20795b33',
            'org_vdc_name': 'Oceans',
        }
        response = self.client.get(
            reverse('Vapps-api:create_vapp_from_template'), query_params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_start_vapp_fail(self):
        """
        Test starting a vApp when in redis queue
        """
        # Given Vapp is in redis cache, Hence busy
        self.assertTrue(self.logged_in)
        self.get_redis_cache(self.vapp_vcd_id_powered_off)

        # Adding to cache
        if not self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_off, True, False)

        response = self.client.get(reverse(
            'Vapps-api:start_vapp', args=[self.vapp_vcd_id_powered_off, self.org_vdc_id_oceans]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = "Error b'Vapp newv is currently busy and is unable to start'"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        #  Since we add, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_off, False, True)

    def test_start_vapp_pass(self):
        """
        Test starting a vApp when it is not in the Redis cache
        """
        self.assertTrue(self.logged_in)
        # Check if the Vapp is busy & exists in redis cache

        self.get_redis_cache(self.vapp_vcd_id_powered_off)

        #  If exists in cache
        if self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_off, False, True)

        response = self.client.get(reverse(
            'Vapps-api:start_vapp', args=[self.vapp_vcd_id_powered_off, self.org_vdc_id_oceans]))
        # Assertion Tests
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        expected_message = "VApp Started Successfully"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we removed, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_off, True, False)

    def test_stop_vapp_fail(self):
        """"
        Test stopping a vApp when in redis queue
        """
        # Given Vapp is in redis cache, Hence busy
        self.assertTrue(self.logged_in)
        self.get_redis_cache(self.vapp_vcd_id_powered_off)

        # Adding to cache
        if not self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_off, True, False)

        response = self.client.get(reverse(
            'Vapps-api:stop_vapp', args=[self.vapp_vcd_id_powered_off, self.org_vdc_id_oceans]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = "Error b'Vapp newv is currently busy and is unable to stop'"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we add, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_off, False, True)

    def test_stop_vapp_pass(self):
        """
        Test stopping a vApp when it is not in the Redis cache
        """
        self.assertTrue(self.logged_in)

        # Check if the Vapp is busy & exists in redis cache
        self.get_redis_cache(self.vapp_vcd_id_powered_on)

        #  If exists in cache
        if self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_on, False, True)

        response = self.client.get(reverse(
            'Vapps-api:stop_vapp', args=[self.vapp_vcd_id_powered_on, self.org_vdc_id_oceans]))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        expected_message = "VApp Stopped Successfully"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we removed, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_on, True, False)

    def test_delete_vapp_fail(self):
        """
        Test deleting a vApp when in redis cache, Hence busy
        """
        self.assertTrue(self.logged_in)
        self.get_redis_cache(self.vapp_vcd_id_powered_off)

        # Adding to cache
        if not self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_off, True, False)

        response = self.client.get(
            reverse('Vapps-api:delete_vapp', args=[self.vapp_vcd_id_powered_off]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = "Error b'Vapp newv is currently busy and is unable to be deleted'"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we add, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_off, False, True)

    def test_delete_vapp_pass(self):
        """
        Test deleting a vApp when it is not in the Redis cache
        """
        self.assertTrue(self.logged_in)

        # Check if the Vapp is busy & exists in redis cache
        self.get_redis_cache(self.vapp_vcd_id_powered_off)

        #  If exists in cache
        if self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_off, False, True)

        response = self.client.get(
            reverse('Vapps-api:delete_vapp', args=[self.vapp_vcd_id_powered_off]))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_message = "VApp Deleted Successfully"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we removed, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_off, True, False)

    def test_poweroff_vapp_fail(self):
        """
        Test powering off a vApp when is in redis cache, Hence busy
        """
        self.assertTrue(self.logged_in)
        # Check if the Vapp is busy & exists in redis cache
        self.get_redis_cache(self.vapp_vcd_id_powered_on)

        # Adding to cache
        if not self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_on, True, False)

        response = self.client.get(reverse(
            'Vapps-api:poweroff_vapp', args=[self.vapp_vcd_id_powered_on, self.org_vdc_id_oceans]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = "Error b'Vapp abc789 is currently busy and is unable to be powered off'"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we add, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_on, False, True)

    def test_poweroff_vapp_pass(self):
        """
        Test powering off a vApp when it is not in the Redis cache
        """
        self.assertTrue(self.logged_in)

        # Check if the Vapp is busy & exists in redis cache
        self.get_redis_cache(self.vapp_vcd_id_powered_on)

        #  If exists in cache
        if self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_on, False, True)

        response = self.client.get(reverse(
            'Vapps-api:poweroff_vapp', args=[self.vapp_vcd_id_powered_on, self.org_vdc_id_oceans]))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_message = "VApp Powered-Off Successfully"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we removed, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_on, True, False)

    def test_stop_and_add_vapp_to_catalog_fail(self):
        """
        Test stopping & adding a vApp to a catalog when in redis queue
        """
        self.assertTrue(self.logged_in)

        self.get_redis_cache(self.vapp_vcd_id_powered_on)

        # Adding to cache
        if not self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_on, True, False)
        query_params = {
            'vapp_vcd_id': self.vapp_vcd_id_powered_on,
            'orgcatalogs': 'Oceans',
            'new_template_name': 'test_new_template_name',
        }
        url = reverse('Vapps-api:stop_and_add_vapp_to_catalog')
        url += '?' + '&'.join([f"{key}={value}" for key,
                              value in query_params.items()])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = "Error b'Vapp abc789 is currently busy and is unable to be powered off. '"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we add, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_on, False, True)

    def test_stop_and_add_vapp_to_catalog_max_catalog(self):
        """
        Test Stopping & Starting a vApp when it is not in the Redis cache
        """
        self.assertTrue(self.logged_in)

        # Check if the Vapp is busy & exists in redis cache
        self.get_redis_cache(self.vapp_vcd_id_powered_on)

        #  If exists in cache
        if self.cache_value:
            self.manipulate_redis_cache(
                self.vapp_vcd_id_powered_on, False, True)

        query_params = {
            'vapp_vcd_id': self.vapp_vcd_id_powered_on,
            'orgcatalogs': 'oceans_catalog',
            'new_template_name': 'test_new_template_name',
        }

        url = reverse('Vapps-api:stop_and_add_vapp_to_catalog')
        url += '?' + '&'.join([f"{key}={value}" for key,
                              value in query_params.items()])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = "Error b'Catalog oceans_catalog already has the max allowed templates, 1. One or more must be removed before more can be added'"
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn(expected_message, response_data['message'])

        # Since we removed, returning to original state
        self.manipulate_redis_cache(
            self.vapp_vcd_id_powered_on, True, False)
