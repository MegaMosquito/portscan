#
# A container providing a REST API for TCP port listener scanning
#
# Written by Glen Darling (mosquito@darlingevil.com), November 2022.
#
FROM ubuntu:latest

# Install required stuff
RUN apt update && apt install -y python3 python3-pip
RUN pip3 install flask waitress

# Setup a workspace directory
RUN mkdir /portscan
WORKDIR /portscan

# Install convenience tools (may omit these in production)
# RUN apt install -y curl jq

# Copy over the portscan files
COPY ./portscan.py /portscan

# Start up the daemon process
CMD python3 portscan.py >/dev/null 2>&1

