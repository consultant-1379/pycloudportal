"""pyvcloud_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from . import views


urlpatterns = [
    path('', views.org_vdc_index, name='org_vdc_index'),
    path('OrgsVdcs', views.org_vdc_index, name='org_vdc_index'),
    path('ProviderVdcs', views.provider_vdc_index, name='ProviderVdcs'),
    path('ProviderVdcs/edit/<int:provider_vdc_id>', views.edit_provider_vdc, name='edit_provider_vdc'),
    path('ProviderVdcs/edit/save_provider_vdc', views.save_provider_vdc, name="save_provider_vdc"),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('jet/', include('jet.urls', 'jet')),  # Django JET URLS
    path('jet/dashboard/', include('jet.dashboard.urls',
         'jet-dashboard')),  # Django JET dashboard URLS
    path('admin/', admin.site.urls),
    path('Vapps/logintest.xml', views.login_for_LMI, name='login_for_LMI'),
    path('Users/login', views.login, name='user_login'),
    path('Users/logout', views.logout, name='user_logout'),
    path('Catalogs', views.catalogs, name='catalogs'),
    path('VappTemplates/index/<str:catalog_name>/<str:org_name>',
         views.vapp_templates, name='vapp_templates'),
    path('VappTemplates/deploy/<str:vapp_template_id>',
         views.create_vapp_from_template, name='create_vapp_from_template'),
    path('VappTemplates/rename/<str:vapp_template_id>',
         views.vapp_templates_rename, name='vapp_templates_rename'),
    path('VappTemplates/delete/<str:vapp_template_id>',
         views.vapp_templates_delete, name='vapp_templates_delete'),
    path('Medias/index/<str:catalog_name>/<str:org_name>',
         views.vapp_templates_media, name='vapp_templates_media'),
    path('Reports', views.show_report, name='show_report'),
    path('Reports/datacenter_report', views.datacenter_report, name='datacenter_report'),
    path('Reports/datacenter_report/download', views.download_datacenter_csv, name='download_datacenter_csv'),
    path('Reports/vapp_report', views.vapp_report, name='vapp_report'),
    path('Reports/vapp_report/datacenter:<str:datacenter_name>/', views.datacenter_vapp_report, name='datacenter_vapp_report'),
    path('Reports/vapp_report/download', views.download_vapp_csv, name='download_vapp_csv'),
    path('Reports/vapp_report/datacenter:<str:datacenter_name>/download', views.download_datacenter_vapp_csv, name='download_datacenter_vapp_csv'),
    path('Reports/historical_reports', views.historical_reports, name='historical_reports'),
    path('Reports/historical_reports/download/<str:reportName>/', views.historical_report_download, name='historical_report_download'),
    path('Groups/', views.list_groups, name='list_groups'),
    path('Groups/add', views.add_groups, name='add_groups'),
    path('Groups/edit/<str:group_id>', views.edit_groups, name='edit_groups'),
    path('Groups/delete/<str:group_id>',
         views.delete_groups, name='delete_groups'),
    path('OrgsVdcs/edit', views.edit_orgvdc,
         name='edit_orgvdc'),
    path('django-rq/', include('django_rq.urls')),
    path('Vapps/', include('Vapps.urls')),
    path('Vapps-api/', include('Vapps.urls_api')),
    path('Vms/', include('VMs.urls_api')),
    path('Views-api/', include('pyvcloud_project.urls_api'))
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += path('__debug__/', include(debug_toolbar.urls)),

handler404 = views.page_not_found_view
