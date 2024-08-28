"""
This module contains test cases for the API views.
"""

from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from pyvcloud_project.models import SppUser


class HomePageAPITestCase(APITestCase):
    """
    Test cases for API views related to the home page.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Set up test data.
        """
        settings.TEST = True
        cls.client = Client()
        cls.username = 'testUser'
        cls.password = 'testUserPassword'
        cls.user = User.objects.create_user(
            username=cls.username,
            password=cls.password,
        )
        # Create SppUser object
        SppUser.objects.create(
            user=cls.user,
            ldap_groups='',
        )

    def setUp(self):
        """
        Set up the test environment.
        """
        # Log in the user
        self.logged_in = self.client.login(
            username=self.username,
            password=self.password
        )

    def test_get_org_vdcs(self):
        """
        Test getting organization virtual data centers.
        """
        self.assertTrue(self.logged_in)
        response = self.client.get(reverse('Views-api:get_org_vdcs'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_message = "Org VDCs retrieved successfully"
        response_data = response.json()

        self.assertIn('message', response_data)
        self.assertEqual(response_data['message'], expected_message)

        expected_keys = ['name', 'org_vdc_id', 'running_tb_limit', 'stored_tb_limit',
                         'vcenter', 'cpu_limit', 'memory_limit', 'created']

        self.assertIn('data', response_data)
        self.assertIsInstance(response_data['data'], list)

        for org_vdc in response_data['data']:
            self.assertIsInstance(org_vdc, dict)
            for key in expected_keys:
                self.assertIn(key, org_vdc)

    def test_get_catalogs(self):
        """
        Test getting catalogs.
        """
        self.assertTrue(self.logged_in)
        response = self.client.get(reverse('Views-api:get_catalogs'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_message = "Catalogs retrieved successfully"
        response_data = response.json()

        self.assertIn('message', response_data)
        self.assertEqual(response_data['message'], expected_message)

        expected_keys = ['name', 'org_name', 'vcd_id']

        self.assertIn('data', response_data)
        self.assertIsInstance(response_data['data'], list)

        for catalog in response_data['data']:
            self.assertIsInstance(catalog, dict)
            for key in expected_keys:
                self.assertIn(key, catalog)

    def test_get_templates_from_catalog(self):
        """
        Test getting templates from a catalog.
        """
        self.assertTrue(self.logged_in)
        catalog_name = 'oceans_catalog'  # Replace with an actual catalog name
        response = self.client.get(
            reverse('Views-api:get_templates_from_catalog', args=[catalog_name]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_message = "All templates from Catalog oceans_catalog retrieved successfully"
        response_data = response.json()

        self.assertIn('message', response_data)
        self.assertEqual(response_data['message'], expected_message)

        self.assertIn('vapp_templates', response_data)
        self.assertIsInstance(response_data['vapp_templates'], list)

        expected_keys = ['id', 'name', 'status',
                         'creationDate', 'numberOfCpus', 'memoryAllocation']

        for template in response_data['vapp_templates']:
            self.assertIsInstance(template, dict)
            for key in expected_keys:
                self.assertIn(key, template)
