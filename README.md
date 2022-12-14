# portscan -- a TCP port listener discovery tool

This code creates a Docker container that  scans for TCP/IP listeners on
IP hosts and provides REST APIs to access this data. The APIs provided
include:

- /portscan/IPv4/PORT/json immediately probe a port on any IP address anywhere
- /portscan/MAC/json return cached port scan info for a particular MAC address
- /portscan/json return a list of MAC addresses that have cached scan results

All results are returned in JSON format. See the examples below.

## Configuring the REST Service:

The first configuration variable must be provided. The default value is the recommended way to configure this tool so it can easily be reached. That is, I suggest you run the **lanscan** tool on a host named **lanscan** that advertises its name using bonjour/zeroconf. I use Raspberry Pi model 3B+ for this and as long as you use Raspberry Pi OS and set the hostnames to that name, this will work beautifully. Here is the variables with its default value:

- **MY_LANSCAN_URL** (default: **http://lanscan.local/lanscan/json**)

You may also choose to override the base URL, address and port number for the REST service:

- **MY_REST_API_BASE_URL** (default: **portscan**)
- **MY_REST_API_HOST_ADDRESS** (default: **0.0.0.0**)
- **MY_REST_API_HOST_PORT** (default: **80**)
- **MY_REST_API_CONTAINER_PORT** (default: **80**)

For performance tuning, you may want to override the number of Python worker threads the code will spawn (**MY_NUM_THREADS**). Otherwise my default value will be used. These threads are all I/O bound witing for socket connections, so they present very little CPU load. I use 50 on a Raspberry Pi 3B+ and I never see the load spike uncomfortbly.

## Starting the REST Service:

To start up the REST service, cd into this directory and run:

```
make
```

Or you can manually do the 2 steps that command does, to first build the container then run it, by using the two steps below:

```
make build
make run
```

## Using the REST Service:

Once the service is running, you may use this command to test the immediate probe (host and port) API:

```
make test
```

If you have a JSON parsing tool like `jq` installed, you may wish to pipe the output through that:

```
make test | jq .
```

## API Usage Examples

Here are some API usage examples:

#### Immediate Host:Port Check:

```
 $ curl -s http://portscan.local/portscan/www.google.con/80/json | jq .
{
  "ip": "www.google.com",
  "port": "80"
}
```

#### Get all currently cached MAC addresses

```
 $ curl -s http://localhost:80/portscan/json | jq .
{
  "macs": [
    "B8:27:EB:AC:14:3E",
    "DC:4F:22:E9:F0:4C",
    "1C:FE:2B:FC:01:A2",
    "24:A1:60:12:C9:63",
    "70:03:9F:CF:EE:D9",
    "B8:27:EB:01:A7:AC",
    "AE:7E:AA:3F:A2:4E",
    "00:50:B6:13:D4:18",
    "DC:4E:F4:05:B9:46",
    "04:92:26:59:21:58",
    ...
    "00:18:DD:01:76:63",
    "70:03:9F:4D:28:54",
    "14:59:C0:93:19:F1",
    "24:A1:60:13:09:21",
    "50:02:91:F2:96:04"
  ]
}
 $ 
```

#### Get the scan details for one specific cached MAC address:

```
 $ curl -s http://localhost:80/portscan/B8:27:EB:AC:14:3E/json | jq .
{
  "host": {
    "ipv4": "192.168.123.12",
    "mac": "B8:27:EB:AC:14:3E"
  },
  "time": {
    "utc": "2022-12-11 21:18:02",
    "prep_sec": 2.7327,
    "scan_sec": 55.9762,
    "total_sec": 58.7089
  },
  "ports": [
    22,
    80
  ],
  "count": 2
}
 $ 
```

## Misc.

If you have feedback, or wish to report issues or contribute fixes or improvements, **Issues** and **PRs** are most welcome!

Written by Glen Darling (mosquito@darlingevil.com), November 2022.

