"""
This module provides functions for importing virtual machine storage details from vSphere to Redis.

"""
from collections import defaultdict
import json
import redis
from pyVmomi import vim
from pyVim.connect import SmartConnect
from pyvcloud_project.models import AuthDetail


def import_vm_storage_from_vsphere(return_dict=False):
    """
    Imports virtual machine storage details from vSphere and saves them to Redis.

    :param return_dict: Flag indicating whether to return the storage details as a dictionary.
    :return: A string indicating the result of the import operation.
    """
    auth_details = AuthDetail.objects.get(name='vsphere')
    host = auth_details.host
    user = auth_details.username
    password = auth_details.password
    conn = SmartConnect(host=host, user=user, pwd=password,
                        disableSslCertValidation=True)
    content = conn.content
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.Datastore], True)
    vapp_vm_vsphere_dict = defaultdict(lambda: defaultdict(dict))
    for ds in container.view:
        for vm in ds.vm:
            vm_parent_name = vm.parent.name
            vm_parent_id = vm_parent_name.split('(')[-1].split(')')[0]
            vm_commited_storage_per_datastore = defaultdict(int)
            vm_provisioned_storage_per_datastore = defaultdict(int)
            vm_name = vm.name.rsplit('-', 1)[0]
            vm_attached_disk = {}
            for device in vm.config.hardware.device:
                if type(device).__name__ == 'vim.vm.device.VirtualDisk':
                    disk_name = device.deviceInfo.label
                    disk_size = device.deviceInfo.summary
                    disk_size = int(float(disk_size.replace(
                        ',', '').replace('KB', '').strip())/1024)
                    vm_attached_disk[disk_name] = disk_size
            for datastore in vm.storage.perDatastoreUsage:
                datastore_name = datastore.datastore.name
                commited_storage_in_bytes = 0 if not datastore.committed else float(
                    datastore.committed)
                provisioned_storage_in_bytes = commited_storage_in_bytes + \
                    0 if not datastore.uncommitted else commited_storage_in_bytes + \
                    float(datastore.uncommitted)
                commited_storage_in_gb = int(
                    commited_storage_in_bytes / 1024 / 1024 / 1024)
                provisioned_storage_in_gb = int(
                    provisioned_storage_in_bytes / 1024 / 1024 / 1024)
                vm_commited_storage_per_datastore[datastore_name] = commited_storage_in_gb
                vm_provisioned_storage_per_datastore[datastore_name] = provisioned_storage_in_gb
            vapp_vm_vsphere_dict[vm_parent_id][vm_name]['datastore_committed'] = vm_commited_storage_per_datastore
            vapp_vm_vsphere_dict[vm_parent_id][vm_name]['datastore_provisioned'] = vm_provisioned_storage_per_datastore
            vapp_vm_vsphere_dict[vm_parent_id][vm_name]['diskinfo'] = vm_attached_disk

    redis_server = redis.Redis()
    vapp_vm_sphere_json = json.dumps(vapp_vm_vsphere_dict)
    redis_server.set('vsphere_vm_storage', vapp_vm_sphere_json)
    if return_dict:
        return vapp_vm_vsphere_dict
    return 'VM storage details imported from vSphere and saved to Redis'
