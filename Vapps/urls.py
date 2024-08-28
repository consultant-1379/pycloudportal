from django.urls import path

from . import views

app_name = 'Vapp'

urlpatterns = [
    path('', views.index, name='vapp_index'),
    path('vapp_diagram/vapp_id:<str:vapp_id>/container_name:<str:container_name>/page:<str:page>',
         views.vapp_diagram, name='vapp_diagram'),
    path('org_vdc_id:<str:org_vdc_id>', views.index, name='vapp_index'),
    path('start_vapp/<str:vapp_vcd_id>/<str:org_vdc_id>',
         views.start_vapp, name='start_vapp'),
    path('stop_vapp/<str:vapp_vcd_id>/<str:org_vdc_id>',
         views.stop_vapp, name='stop_vapp'),
    path('delete_vapp/<str:vapp_vcd_id>',
         views.delete_vapp, name='delete_vapp'),
    path('poweroff_vapp/<str:vapp_vcd_id>/<str:org_vdc_id>',
         views.poweroff_vapp, name='poweroff_vapp'),
    path('vapp_poweroff_and_delete/<str:vapp_vcd_id>/<str:org_vdc_id>/<str:vapp_name>',
         views.vapp_poweroff_and_delete, name='vapp_poweroff_and_delete'),
    path('rename_vapp/<str:vapp_vcd_id>',
         views.rename_vapp, name='rename_vapp'),
    path('vapp_rename_form/<str:vapp_vcd_id>/<str:vapp_name>',
         views.rename_vapp_form, name='vapp_rename_form'),
    path('recompose_vapp/<str:vapp_vcd_id>',
         views.recompose_vapp, name='recompose_vapp'),
    path('add_vapp_to_catalog', views.add_vapp_to_catalog,
         name='add_vapp_to_catalog'),
    path('tasks/vapp_vcd_id:<str:vapp_vcd_id>',
         views.vapp_tasks, name='vapp_tasks'),
    path('vapp_share_unshare/<str:vapp_vcd_id>/<str:org_vdc_id>/<str:vapp_name>/<str:share_unshare>',
         views.toggle_vapp_shared_state, name='vapp_share_unshare'),
]
