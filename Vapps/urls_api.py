from django.urls import path

from . import views_api

app_name = 'Vapps-api'

urlpatterns = [
    # API endpoints for each URL
    path('start_vapp/<str:vapp_vcd_id>/<str:org_vdc_id>/',
         views_api.start_vapp, name='start_vapp'),
    path('start_vapp_xml/<str:vapp_vcd_id>/<str:org_vdc_id>/',
         views_api.start_vapp_xml, name='start_vapp_xml'),

    path('stop_vapp/<str:vapp_vcd_id>/<str:org_vdc_id>/',
         views_api.stop_vapp, name='stop_vapp'),
    path('stop_vapp_xml/<str:vapp_vcd_id>/<str:org_vdc_id>/',
         views_api.stop_vapp_xml, name='stop_vapp_xml'),

    path('delete_vapp/<str:vapp_vcd_id>/',
         views_api.delete_vapp, name='delete_vapp'),
    path('delete_vapp_xml/<str:vapp_vcd_id>/',
         views_api.delete_vapp_xml, name='delete_vapp_xml'),

    path('poweroff_vapp/<str:vapp_vcd_id>/<str:org_vdc_id>/',
         views_api.poweroff_vapp, name='poweroff_vapp'),
    path('poweroff_vapp_xml/<str:vapp_vcd_id>/<str:org_vdc_id>/',
         views_api.poweroff_vapp_xml, name='poweroff_vapp_xml'),

    path('get_vapps/org_vdc_id:<str:org_vdc_id>',
         views_api.get_vapps, name='get_vapps'),
    path('get_vapps_xml/org_vdc_id:<str:org_vdc_id>',
         views_api.get_vapps_xml, name='get_vapps_xml'),

    path('get_vapp_status_xml/<str:org_vdc_id>/<str:vAppName>/',
         views_api.get_vapp_status_xml, name='get_vapp_status_xml'),

    path('create_vapp_from_template', views_api.create_vapp_from_template,
         name='create_vapp_from_template'),
    path('create_vapp_from_template_xml', views_api.create_vapp_from_template_xml,
         name='create_vapp_from_template_xml'),

    path('stop_and_add_vapp_to_catalog', views_api.stop_and_add_vapp_to_catalog,
         name='stop_and_add_vapp_to_catalog'),
    path('stop_and_add_vapp_to_catalog_xml', views_api.stop_and_add_vapp_to_catalog_xml,
         name='stop_and_add_vapp_to_catalog_xml'),

    path('recompose_vapp_xml/<str:vapp_vcd_id>',
         views_api.recompose_vapp_xml, name='recompose_vapp_xml'),
]
