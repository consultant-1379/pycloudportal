from django.urls import path
from . import views, views_api

app_name = 'Vms'

urlpatterns = [
    path('get_vms/vapp_vcd_id:<str:vapp_vcd_id>',
         views_api.get_vms, name='get_vms'),
    path('get_vms_xml/vapp_vcd_id:<str:vapp_vcd_id>',
         views_api.get_vms_xml, name='get_vms_xml'),
    path('get_vms_from_template/template_id:<str:template_id>',
         views_api.get_vms_from_template, name='get_vms_from_template'),
    path('get_vms_from_template_xml/template_id:<str:template_id>',
         views_api.get_vms_from_template_xml, name='get_vms_from_template_xml'),
    path('poweron_api/vm_name:<str:vm_name>',
         views_api.poweron_vm, name='poweron_vm'),
    path('poweroff_api/vm_name:<str:vm_name>',
         views_api.poweroff_vm, name='poweroff_vm'),
    path('reset_api/vm_name:<str:vm_name>',
         views_api.reset_vm, name='poweron_vm'),
    path('set_boot_device_api/boot_devices:<str:boot_device>/vm_name:<str:vm_name>',
         views_api.change_boot_order, name='change_boot_order'),
    path('vapp_id:<str:vapp_id>',
         views.index, name='vm_index'),
    path('vapptemplate_index/template_id:<str:template_id>',
         views.vm_templates, name='vm_templates'),
    path('power_on_vm/vapp_id:<str:vapp_id>/vm_id:<str:vm_id>',
         views.power_on_vm, name='power_on_vm'),
    path('power_off_vm/vapp_id:<str:vapp_id>/vm_id:<str:vm_id>',
         views.power_off_vm, name='power_off_vm'),
    path('shutdown_vm/vapp_id:<str:vapp_id>/vm_id:<str:vm_id>',
         views.shutdown_vm, name='shutdown_vm'),
    path('delete_vm/vapp_id:<str:vapp_id>/vm_id:<str:vm_id>',
         views.delete_vm, name='delete_vm'),
    path('tasks/vm_id:<str:vm_id>',
         views.vm_tasks, name='vm_tasks'),
]
