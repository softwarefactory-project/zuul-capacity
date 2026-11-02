# zuul-capacity

This is a custom prometheus exporter to provide the available capacity as a metric:

```ShellSession
$ uv run ./zuul-capacity.py --help
usage: zuul-capacity.py [-h] [--nodepool FILE] [--port PORT]

options:
  -h, --help       show this help message and exit
  --nodepool FILE  The list of providers
  --port PORT      The prometheus scrap target listening port
```

To run this service, you must provide a nodepool configuration and a clouds.yaml.

Nodepool `aws` driver providers (e.g. one backed by
[prekv](https://gitlab.com/softwarefactory-project/prekv), which exposes a
KubeVirt cluster through an EC2-compatible API) are also discovered from the
nodepool configuration: each such provider needs a `profile-name` pointing at
a profile in the standard AWS config/credentials files (`AWS_CONFIG_FILE` /
`~/.aws/config`), exactly as Nodepool's own `aws` driver expects. Instance
counts and CPU/memory come from `DescribeInstances`/`DescribeInstanceTypes`;
disk comes from `DescribeVolumes`, which requires `prekv` 0.6+ since earlier
versions always reported an empty volume set.

## Changelog

### 0.6.0

- Added `aws` driver provider support (e.g. for prekv), including disk usage
  via `DescribeVolumes`

### 0.5.0

- Added a zuul_instances_disk metric

### 0.4.0

- Initial release
