#
# portscan  -- implements a TCP listener discovery REST API service
#
# Written by Glen Darling (mosquito@darlingevil.com), November 2022.
#

NAME         := portscan
DOCKERHUB_ID := ibmosquito
VERSION      := 1.0.0

# You may optionally override these "MY_" variables in your shell environment
MY_REST_API_BASE_URL  ?= /$(NAME)
MY_REST_API_PORT      ?= 8004# This is the *host* port. Container port is 80.
MY_NUM_PROCESSES      ?= 50

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
	  -e MY_NUM_PROCESSES=$(MY_NUM_PROCESSES) \
	  -e MY_REST_API_BASE_URL=$(MY_REST_API_BASE_URL) \
	  -e MY_REST_API_PORT=80 \
	  -p $(MY_REST_API_PORT):80/tcp \
	  $(DOCKERHUB_ID)/$(NAME):$(VERSION) /bin/bash

# Run the container as a daemon (build not forecd here, so build it first)
run: stop
	docker run -d --restart unless-stopped \
	  --name $(NAME) \
	  -e MY_NUM_PROCESSES=$(MY_NUM_PROCESSES) \
	  -e MY_REST_API_BASE_URL=$(MY_REST_API_BASE_URL) \
	  -e MY_REST_API_PORT=80 \
	  -p $(MY_REST_API_PORT):80/tcp \
	  $(DOCKERHUB_ID)/$(NAME):$(VERSION)

# Test the service by sending a JSON port scan request
# You may wish to pipe the output to `jq`, e.g., `make test | jq .`
test:
	@curl -s localhost:$(MY_REST_API_PORT)$(MY_REST_API_BASE_URL)/www.google.com/80/json

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

# Declare all of these non-file-system targets as .PHONY
.PHONY: default build dev run test exec push stop clean

