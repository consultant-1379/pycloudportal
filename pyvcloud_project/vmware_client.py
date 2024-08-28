"""
This module provides a singleton implementation of a VMWare client using pyvcloud library.

The VMWareClientSingleton class is responsible for creating a single instance of the VMWare client
and ensuring that only one instance is created throughout the application. It utilizes thread
locking to ensure thread-safety during instance creation.

"""

import threading
import urllib3
from pyvcloud.vcd.client import Client, BasicLoginCredentials, UnauthorizedException
from pyvcloud_project.models import AuthDetail

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class VMWareClientSingleton:
    __instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            try:
                cls.__instance.client.get_admin()
            except (UnauthorizedException, AttributeError, TypeError):
                cls.__instance = \
                    super().__new__(cls)
                cls.client = cls._login()
        return cls.__instance

    @staticmethod
    def _login():
        auth_details = AuthDetail.objects.get(name='vcd')
        client = None
        credentials = {
            'user': auth_details.username,
            'password': auth_details.password,
            'org': auth_details.org,
            'host': auth_details.host,
            'api_version': auth_details.api_version,
            'verify_ssl_certs': False
        }
        try:
            user = credentials['user']
            password = credentials['password']
            org = credentials['org']
            host = credentials['host']
            api_version = credentials['api_version']
            verify_ssl_certs = credentials['verify_ssl_certs']
            client = Client(host,
                            log_file='pyvcloud.log',
                            api_version=api_version,
                            log_requests=True,
                            log_headers=True,
                            log_bodies=True,
                            verify_ssl_certs=verify_ssl_certs)

            client.set_credentials(BasicLoginCredentials(user, org, password))
        except (UnauthorizedException, AttributeError, TypeError) as ex:
            print(
                f'Login failed for user {user} to org {org}. Exception: {ex}')
        return client
