"""
URL configuration for Views API.
"""

from django.urls import path
from . import views_api

app_name = 'Views-api'

urlpatterns = [
    path('get_org_vdcs', views_api.get_org_vdcs, name='get_org_vdcs'),
    path('get_org_vdcs_xml', views_api.get_org_vdcs_xml, name='get_org_vdcs_xml'),
    path('get_catalogs', views_api.get_catalogs, name='get_catalogs'),
    path('get_catalogs_xml', views_api.get_catalogs_xml, name='get_catalogs_xml'),
    path('get_templates_from_catalog/<str:catalog_name>',
         views_api.get_templates_from_catalog, name='get_templates_from_catalog'),
    path('get_templates_from_catalog_xml/<str:catalog_name>',
         views_api.get_templates_from_catalog_xml, name='get_templates_from_catalog_xml')
]
