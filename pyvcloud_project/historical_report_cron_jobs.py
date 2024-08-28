from collections import defaultdict
import logging
import csv
import os
from datetime import datetime
from pyvcloud_project.vmware_client import VMWareClientSingleton
from pyvcloud_project.models import OrgVdcs, Vapps, HistoricalReport
from pyvcloud_project.utils import orgvdc_utils, vapp_utils

logger = logging.getLogger(__name__)

def VappReportDownloadCronJob():
    try:
        client = VMWareClientSingleton().client
        vapps_data = Vapps.objects.all()
        vapp_info_list = [vapp_utils.get_vapp_info(vapp, client) for vapp in vapps_data]
        org_ids = list(set([vapp.org_vdc_obj.org_vdc_id for vapp in vapps_data]))
        org_vapps = defaultdict(list)

        for org_id in org_ids:
            org_vapps[org_id] = orgvdc_utils.get_vapp_resources(client, org_id)

        for vapp_info in vapp_info_list:
            vapp_org_vdc_id = vapp_info["org_vdc_id"]
            vapp_resource_data = org_vapps[vapp_org_vdc_id].get(
                vapp_info["vapp_vcd_id"]
            )
            if vapp_resource_data:
                vapp_info["running_cpu"] = vapp_resource_data["cpu_on_count"]
                vapp_info["running_memory"] = vapp_resource_data["memory_on_count"]

        logger.info(f"{datetime.now()} - vApp Report Created Successfully")

        currentTime = datetime.now()
        report_folder = "/opt/pycloudportal/HistoricalReports"
        os.makedirs(report_folder, exist_ok=True)
        reportFilename = os.path.join(
            report_folder, currentTime.strftime("%Y-%m-%d--%H-%M-%S_vapp_report.csv")
        )

        filename = os.path.basename(reportFilename)

        with open(reportFilename, "w", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(
                [
                    "Datacenter Name",
                    "vApp Name",
                    "Status",
                    "Gateway",
                    "Created By",
                    "Creation Date",
                    "Running CPUs",
                    "Running Memory (GB)",
                    "Origin Catalog Name",
                    "Origin Template Name",
                ]
            )

            for vapp_info in vapp_info_list:
                csv_writer.writerow(
                    [
                        vapp_info["catalog_name"],
                        vapp_info["name"],
                        vapp_info["vapp_power_state"],
                        vapp_info["gateway"],
                        vapp_info["created_by"],
                        vapp_info["creation_date"],
                        vapp_info["running_cpu"],
                        vapp_info["running_memory"],
                        vapp_info["origin_catalog_name"],
                        vapp_info["origin_template_name"],
                    ]
                )

        vapp_report = HistoricalReport(name=filename)
        vapp_report.save()
        logger.info(f"{datetime.now()} - vApp Report Downloaded Successfully")
    except Exception as e:
        logger.error(f"An error occurred in VAPP report: {str(e)}")

def DatacenterReportDownloadCronJob():
    try:
        org_vdcs = OrgVdcs.objects.all()
        client = VMWareClientSingleton().client
        datacenter_info = []

        for org_vdc in org_vdcs:
            orgvdc_id = org_vdc.org_vdc_id
            running_vapps, *_ = orgvdc_utils.count_vapps(client, orgvdc_id)
            total_cpu_on_count = 0
            total_memory_on_count = 0
            vapp_resources = orgvdc_utils.get_vapp_resources(client, orgvdc_id)

            for vapp_info in vapp_resources.items():
                vapp_data = vapp_info[1]
                total_cpu_on_count += vapp_data.get("cpu_on_count")
                total_memory_on_count += vapp_data.get("memory_on_count")

            datacenter_info.append(
                {
                    "datacenter_name": org_vdc.name,
                    "provider_name": org_vdc.provider_vdc_obj,
                    "running_cpus": total_cpu_on_count,
                    "running_cpus_quota": org_vdc.cpu_limit,
                    "unused_running_cpus_quota": (
                        org_vdc.cpu_limit - total_cpu_on_count
                    ),
                    "running_memory_gb": total_memory_on_count,
                    "running_memory_quota_gb": org_vdc.memory_limit,
                    "unused_running_memory_quota_gb": (
                        org_vdc.memory_limit - total_memory_on_count
                    ),
                    "running_vApps": running_vapps,
                    "running_vApps_quota": org_vdc.running_tb_limit,
                    "unused_running_vApps_quota": (
                        org_vdc.running_tb_limit - running_vapps
                    ),
                    "total_vApps": len(vapp_resources),
                    "total_vApps_quota": org_vdc.stored_tb_limit,
                    "unused_total_vApps_quota": (
                        org_vdc.stored_tb_limit - len(vapp_resources)
                    ),
                }
            )

        logger.info(f"{datetime.now()} - Datacenter Report Created Successfully")

        datacenter_info_list = datacenter_info
        currentTime = datetime.now()
        report_folder = "/opt/pycloudportal/HistoricalReports"
        os.makedirs(report_folder, exist_ok=True)
        reportFilename = os.path.join(
            report_folder,
            currentTime.strftime("%Y-%m-%d--%H-%M-%S_datacenter_report.csv"),
        )
        filename = os.path.basename(reportFilename)

        with open(reportFilename, "w", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(
                [
                    "Datacenter Name",
                    "Provider Name",
                    "Running CPUs",
                    "Running CPUs Quota",
                    "Unused Running CPUs Quota",
                    "Running Memory (GB)",
                    "Running Memory Quota (GB)",
                    "Unused Running Memory Quota (GB)",
                    "Running vApps",
                    "Running vApps Quota",
                    "Unused Running vApps Quota",
                    "Total vApps",
                    "Total vApps Quota",
                    "Unused Total vApps Quota",
                ]
            )

            for datacenter_info in datacenter_info_list:
                csv_writer.writerow(
                    [
                        datacenter_info["datacenter_name"],
                        datacenter_info["provider_name"],
                        datacenter_info["running_cpus"],
                        datacenter_info["running_cpus_quota"],
                        datacenter_info["unused_running_cpus_quota"],
                        datacenter_info["running_memory_gb"],
                        datacenter_info["running_memory_quota_gb"],
                        datacenter_info["unused_running_memory_quota_gb"],
                        datacenter_info["running_vApps"],
                        datacenter_info["running_vApps_quota"],
                        datacenter_info["unused_running_vApps_quota"],
                        datacenter_info["total_vApps"],
                        datacenter_info["total_vApps_quota"],
                        datacenter_info["unused_total_vApps_quota"],
                    ]
                )

        datacenter_report = HistoricalReport(name=filename)
        datacenter_report.save()
        logger.info(f"{datetime.now()} - Datacenter Report Downloaded Successfully")
    except Exception as e:
        logger.error(f"An error occurred in Datacenter report: {str(e)}")