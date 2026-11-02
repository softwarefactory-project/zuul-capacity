# Copyright © 2024 Tristan de Cacqueray
# SPDX-License-Identifier: Apache-2.0
#
# The purpose of this script is to collect resources usage of nodepool provider.
# The metrics are available as a prometheus scrap target.

import argparse
import openstack
import boto3
import logging
import time
import yaml
from dataclasses import dataclass
from prometheus_client import start_http_server, Gauge, Counter

log = logging.getLogger("zuul-capacity")


@dataclass
class Resource:
    mem: int
    cpu: int
    disk: int

    def from_server(server):
        flavor = server["flavor"]
        if flavor["ram"] == 0:
            return None
        return Resource(flavor["ram"], flavor["vcpus"], flavor["disk"])

    def from_flavor(flavors, cloud, server):
        flavor_id = server["flavor"].id
        if flavor_id not in flavors:
            log.info("Requesting flavor %s", flavor_id)
            flavors[flavor_id] = cloud.get_flavor(flavor_id)
        flavor = flavors[flavor_id]
        return Resource(flavor["ram"], flavor["vcpus"], flavor["disk"])

    def from_aws_instance(instance_types, volume_sizes, instance):
        instance_type = instance_types[instance["InstanceType"]]
        mem = instance_type["MemoryInfo"]["SizeInMiB"]
        cpu = instance_type["VCpuInfo"]["DefaultVCpus"]
        disk = sum(
            volume_sizes.get(bdm["Ebs"]["VolumeId"], 0)
            for bdm in instance.get("BlockDeviceMappings", [])
            if "Ebs" in bdm
        )
        return Resource(mem, cpu, disk)


def get_resources(flavors, cloud):
    "Get the cloud resources."
    resources = []
    for server in cloud.compute.servers():
        try:
            if resource := Resource.from_server(server):
                resources.append(resource)
            else:
                resources.append(Resource.from_flavor(flavors, cloud, server))
        except Exception as e:
            log.exception("Couldn't get server resource %s: %s", server, e)
    return resources


def get_aws_resources(instance_types, ec2):
    "Get the resources of a Nodepool aws driver provider (e.g. backed by prekv)."
    instances = []
    for page in ec2.get_paginator("describe_instances").paginate():
        for reservation in page["Reservations"]:
            instances.extend(reservation["Instances"])

    unknown_types = {i["InstanceType"] for i in instances} - instance_types.keys()
    if unknown_types:
        log.info("Requesting instance types %s", unknown_types)
        described = ec2.describe_instance_types(InstanceTypes=list(unknown_types))
        for it in described["InstanceTypes"]:
            instance_types[it["InstanceType"]] = it

    volume_ids = [
        bdm["Ebs"]["VolumeId"]
        for instance in instances
        for bdm in instance.get("BlockDeviceMappings", [])
        if "Ebs" in bdm
    ]
    volume_sizes = {}
    if volume_ids:
        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate(VolumeIds=volume_ids):
            for volume in page["Volumes"]:
                volume_sizes[volume["VolumeId"]] = volume["Size"]

    resources = []
    for instance in instances:
        try:
            resources.append(
                Resource.from_aws_instance(instance_types, volume_sizes, instance)
            )
        except Exception as e:
            log.exception("Couldn't get instance resource %s: %s", instance, e)
    return resources


@dataclass
class Provider:
    max_server: int
    driver: str
    cloud: any

    def from_nodepool(provider):
        driver = provider.get("driver")
        if driver == "aws":
            session = boto3.Session(profile_name=provider["profile-name"])
            cloud = session.client("ec2")
        else:
            cloud = openstack.connect(cloud=provider["cloud"])
        return Provider(provider.get("max-server", -1), driver, cloud)


def get_providers(nodepool_yaml):
    "Get the cloud provider from the nodepool config."
    providers = dict()
    nodepool = yaml.safe_load(open(nodepool_yaml))
    for provider in nodepool.get("providers", []):
        driver = provider.get("driver")
        if (driver == "openstack" and provider.get("cloud")) or (
            driver == "aws" and provider.get("profile-name")
        ):
            providers[provider.get("name", "unknown")] = Provider.from_nodepool(
                provider
            )
    return providers


def update_provider_metric(metrics, flavors, instance_types, name, provider):
    if provider.driver == "aws":
        resources = get_aws_resources(instance_types, provider.cloud)
    else:
        resources = get_resources(flavors, provider.cloud)
    metrics["instances"].labels(cloud=name).set(len(resources))
    cpu, mem, disk = 0, 0, 0
    for resource in resources:
        cpu += resource.cpu
        mem += resource.mem
        disk += resource.disk
    metrics["cpu"].labels(cloud=name).set(cpu)
    metrics["mem"].labels(cloud=name).set(mem)
    metrics["disk"].labels(cloud=name).set(disk)


def update_providers_metric(metrics, flavors, instance_types, providers):
    for name, provider in providers.items():
        try:
            update_provider_metric(metrics, flavors, instance_types, name, provider)
        except Exception as e:
            log.exception("Couldn't get provider %s: %s", name, e)
            metrics["error"].labels(cloud=name).inc()


def usage():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--nodepool",
        metavar="FILE",
        default="/etc/nodepool/nodepool.yaml",
        help="The list of providers",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="The prometheus scrap target listening port",
    )
    return parser.parse_args()


def main():
    args = usage()
    logging.basicConfig(level=logging.INFO)

    metrics = dict(
        instances=Gauge("zuul_instances_total", "Instance count", ["cloud"]),
        mem=Gauge("zuul_instances_mem", "Memory usage", ["cloud"]),
        cpu=Gauge("zuul_instances_cpu", "VCPU usage", ["cloud"]),
        disk=Gauge("zuul_instances_disk", "Disk usage", ["cloud"]),
        error=Counter("zuul_provider_error", "API call error", ["cloud"]),
    )

    providers = get_providers(args.nodepool)
    flavors = dict()
    instance_types = dict()

    update_providers_metric(metrics, flavors, instance_types, providers)

    # Initialize connection
    log.info("Starting exporter at :%d for %d provider", args.port, len(providers))
    start_http_server(args.port)

    while True:
        time.sleep(300)
        update_providers_metric(metrics, flavors, instance_types, providers)


if __name__ == "__main__":
    main()
