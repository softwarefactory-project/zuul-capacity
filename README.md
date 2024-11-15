# zuul-capacity

This is a custom prometheus exporter to provide the available capacity as a metric:

```ShellSession
$ uv run ./zuul-capacity.py
usage: zuul-capacity.py [-h] [--nodepool FILE] [--port PORT]

options:
  -h, --help       show this help message and exit
  --nodepool FILE  The list of providers
  --port PORT      The prometheus scrap target listening port
```

To run this service, you must provide a nodepool configuration and a clouds.yaml.
