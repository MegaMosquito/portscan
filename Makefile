#
# portscan  -- implements a TCP listener discovery REST API service
#
# Written by Glen Darling (mosquito@darlingevil.com), November 2022.
#

NAME         := portscan
DOCKERHUB_ID := ibmosquito
VERSION      := 1.0.0

# *****************************************************************************
# NOTE: If any of the following capitalized "MY_..." variables exist in your
# shell environment, then  your shell values will be used instead of the
# values provided here in the Makefile.
# *****************************************************************************

# The URL must be provided for the lanscan REST API service
MY_LANSCAN_URL         ?=http://lanscan.local/lanscan/json

# Where will HTTP requests be served (e.g., port 80 on all host interfaces)?
MY_REST_API_BASE_URL       ?=$(NAME)
MY_REST_API_HOST_ADDRESS   ?=0.0.0.0
MY_REST_API_HOST_PORT      ?=80
MY_REST_API_CONTAINER_PORT ?=80

# The (host) cache directory location
MY_CACHE_DIRECTORY     ?=$(HOME)/cache

# The number of threads in the thread pool
MY_NUM_THREADS         ?= 50

# Running `make` with no target builds and runs this as a restarting daemon
default: build run

# Build the container and tag it
build:
	docker build -t $(DOCKERHUB_ID)/$(NAME):$(VERSION) .

# Running `make dev` will setup a working environment, just the way I like it.
# On entry to the container's bash shell, run `cd /outside` to work here.
dev: stop build
	docker run -it --volume `pwd`:/outside \
	  --name $(NAME) \
	  --volume /var/run/dbus:/var/run/dbus \
	  --volume /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket \
	  --volume $(MY_CACHE_DIRECTORY):/cache \
	  -p $(MY_REST_API_HOST_ADDRESS):$(MY_REST_API_HOST_PORT):$(MY_REST_API_CONTAINER_PORT) \
	  -e MY_LANSCAN_URL=$(MY_LANSCAN_URL) \
	  -e MY_REST_API_BASE_URL=$(MY_REST_API_BASE_URL) \
	  -e MY_REST_API_PORT=$(MY_REST_API_CONTAINER_PORT) \
	  -e MY_NUM_THREADS=$(MY_NUM_THREADS) \
	  $(DOCKERHUB_ID)/$(NAME):$(VERSION) /bin/bash

# Run the container as a daemon (build not forecd here, so build it first)
run: stop
	docker run -d --restart unless-stopped \
	  --name $(NAME) \
	  --volume /var/run/dbus:/var/run/dbus \
	  --volume /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket \
	  --volume $(MY_CACHE_DIRECTORY):/cache \
	  -p $(MY_REST_API_HOST_ADDRESS):$(MY_REST_API_HOST_PORT):$(MY_REST_API_CONTAINER_PORT) \
	  -e MY_LANSCAN_URL=$(MY_LANSCAN_URL) \
	  -e MY_REST_API_BASE_URL=$(MY_REST_API_BASE_URL) \
	  -e MY_REST_API_PORT=$(MY_REST_API_CONTAINER_PORT) \
	  -e MY_NUM_THREADS=$(MY_NUM_THREADS) \
	  $(DOCKERHUB_ID)/$(NAME):$(VERSION)

# Test the service by sending a JSON port scan request
# You may wish to pipe the output to `jq`, e.g., `make test | jq .`
test:
	@curl -s http://localhost:$(MY_REST_API_HOST_PORT)/$(MY_REST_API_BASE_URL)/www.google.com/80/json

# Enter the context of the daemon container
exec:
	@docker exec -it ${NAME} /bin/sh

# Push the conatiner to DockerHub (you need to `docker login` first of course)
push:
	docker push $(DOCKERHUB_ID)/$(NAME):$(VERSION) 

# Stop the daemon container
stop:
	@docker rm -f ${NAME} >/dev/null 2>&1 || :

# Stop the daemon container, and cleanup
clean: stop
	@docker rmi -f $(DOCKERHUB_ID)/$(NAME):$(VERSION) >/dev/null 2>&1 || :

# Show some cache stats
stats:
	@echo "Number of MACs scanned and cached currently:"
	@find ~/cache -type f | wc -l
	@echo "Total number of TCP ports scanned from cached hosts currently:"
	@find ~/cache -type f | wc -l | awk '{print $$1 * 65535;}'
	@echo "Count of unique open port numbers found on the LAN so far:"
	@find ~/cache -type f | xargs jq '.ports[]' | wc -l
	@echo "Scan timing for all files currently in the cache (in seconds):"
	@find ~/cache -type f | xargs jq .time.total_sec | python3 -c "import sys; nums = [float(n.strip()) for n in sys.stdin]; print(f'Min: {min(nums):0.0f}, Max: {max(nums):0.0f}, Total: {sum(nums):0.0f}, Mean: {sum(nums)/len(nums):0.0f}.')"

# Declare all of these non-file-system targets as .PHONY
.PHONY: default build dev run test exec push stop clean stats

