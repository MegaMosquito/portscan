# portscan -- a TCP port listener discovery tool

This code creates a Docker container that provides a basic REST service that
checks for TCP/IP listeners on IP hosts. Three APIs are provided for:

- single host (anywhere), simgle port (responds almost immediately)
- single host (anywhere), range of ports (may take a while to respond)
- single port, on a range of hosts on the same "/24" LAN (may take a while to respond)

The results are returned in JSON format. See the examples below.

## Configuring the REST Service:

You may choose to override the base URL for the REST service (**MY_REST_API_BASE_URL**), and/or the host port that the REST service binds to (**MY_REST_API_PORT**).

For performance tuning, you may want to override the number of Python `multiprocessing`-module processes the code will spawn (**MY_NUM_PROCESSES**). Otherwise my default values will be used. In general more processes is better for faster convergence to discovery of the full set of MACs on your LAN, but there are tradeoffs. Processes take longer than threads to spawn at the start of the program and each process uses memory and creates CPU load on the host. I have set the default number of processes to 50, which seems to be a good compromise for my usage. Of course, if I am only requesting a scan of 10 ports on one host, that's not very efficient. But it works well for deep scans and I feel it is not too slow for my small scans. You may wish to experiment with different numbers of processes to tune things for your tastes.

## Starting the REST Service:

To start up the REST service, you must first build the container then run it using the two steps below:

```
make build
make run
```

## Using the REST Service:

Once the service is running, you may use this command to test the single host and single port API:

```
make test
```

If you have a JSON parsing tool like `jq` installed, you may wish to pipe the output through that:

```
make test | jq .
```

## Examples

Here are some usage examples:

#### Single Host, Single Port

```
pi@netmon:~/git/scan $ make test | jq .
{
  "ip": "www.google.com",
  "port": "80"
}
```

#### Single Host, Range of Ports

```
pi@netmon:~/git/scan $ curl -s localhost:8004/portscan/ports/192.168.123.82/1/1023/json | jq .
{
  "time": {
    "prep_sec": 1.2787,
    "scan_sec": 0.0208,
    "total_sec": 1.2994
  },
  "scan": [
    {
      "ip": "192.168.123.82",
      "port": "22"
    },
    {
      "ip": "192.168.123.82",
      "port": "80"
    },
    {
      "ip": "192.168.123.82",
      "port": "443"
    }
  ]
}
```

#### Single Port, Range of Hosts on the same "/24" LAN

```
pi@netmon:~/git/scan $ curl -s localhost:8004/portscan/ips/192.168.123.1/192.168.123.99/80/json | jq .
{
  "time": {
    "prep_sec": 0.3732,
    "scan_sec": 9.0851,
    "total_sec": 9.4583
  },
  "scan": [
    {
      "ip": "192.168.123.1",
      "port": "80"
    },
    {
      "ip": "192.168.123.2",
      "port": "80"
    },
    {
      "ip": "192.168.123.4",
      "port": "80"
    },
    {
      "ip": "192.168.123.5",
      "port": "80"
    },
    {
      "ip": "192.168.123.30",
      "port": "80"
    },
    {
      "ip": "192.168.123.80",
      "port": "80"
    },
    {
      "ip": "192.168.123.82",
      "port": "80"
    },
    {
      "ip": "192.168.123.91",
      "port": "80"
    }
  ]
}
```

## Misc.

If you have feedback, or wish to report issues or contribute fixes or improvements, **Issues** and **PRs** are most welcome!

Written by Glen Darling (mosquito@darlingevil.com), November 2022.

