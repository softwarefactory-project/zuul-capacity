# Copyright © 2024 Tristan de Cacqueray
# SPDX-License-Identifier: Apache-2.0

import argparse, openstack, logging, time, yaml
from dataclasses import dataclass
from prometheus_client import start_http_server, Gauge

log = logging.getLogger(__name__)

@dataclass
class Resource:
    mem: int
    cpu: int

    def from_server(server):
        flavor = server["flavor"]
        return Resource(flavor["ram"], flavor["vcpus"])

def get_resources(cloud):
    "Get the cloud resources."
    resources = []
    for server in cloud.compute.servers():
        try:
            resources.append(Resource.from_server(server))
        except Exception as e:
            log.exception("Couldn't get server resource", e, server)
    return resources

@dataclass
class Provider:
    max_server: int
    cloud: any

    def from_nodepool(provider):
        return Provider(
            provider.get("max-server", -1),
            openstack.connect(cloud=provider["cloud"])
        )

def get_providers(nodepool_yaml):
    "Get the cloud provider from the nodepool config."
    providers = dict()
    nodepool = yaml.safe_load(open(nodepool_yaml))
    for provider in nodepool["providers"]:
        if provider["driver"] == "openstack":
            providers[provider["name"]] = Provider.from_nodepool(provider)
    return providers

def usage():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodepool", metavar="FILE", required=True)
    return parser.parse_args()

def main():
    args = usage()
    logging.basicConfig(level=logging.INFO)

    metrics = dict(
        instances = Gauge('zuul_instances_total', 'Instance count', ['cloud']),
        mem = Gauge('zuul_instances_mem', 'Memory usage', ['cloud']),
        cpu = Gauge('zuul_instances_cpu', 'VCPU usage', ['cloud']),
    )

    providers = get_providers(args.nodepool)

    # Initialize connection
    log.info("Starting exporter at :8080 for %d provider", len(providers))
    start_http_server(8080)

    while True:
        for (name, provider) in providers.items():
            resources = get_resources(provider.cloud)
            metrics["instances"].labels(cloud=name).set(len(resources))
            cpu, mem = 0, 0
            for resource in resources:
                cpu += resource.cpu
                mem += resource.mem
            metrics["cpu"].labels(cloud=name).set(cpu)
            metrics["mem"].labels(cloud=name).set(mem)
        time.sleep(300)



if __name__ == "__main__":
    main()
