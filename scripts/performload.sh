#!/bin/bash

EXTERNAL_IP=$1

while true; do
  curl -s http://$EXTERNAL_IP/api/navigation > /dev/null
done
