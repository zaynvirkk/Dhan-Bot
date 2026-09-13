#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?usage: create_gcp_vm.sh PROJECT_ID}"
GCLOUD_BIN="${GCLOUD_BIN:-gcloud}"
REGION=asia-south1
ZONE=asia-south1-a
INSTANCE=sablestone-dhan-cas
ADDRESS=sablestone-dhan-cas-ip
gc() { "$GCLOUD_BIN" --project="$PROJECT_ID" --quiet "$@"; }

gc services enable compute.googleapis.com iap.googleapis.com
if ! gc compute networks describe dhan-cas-network >/dev/null 2>&1; then
  gc compute networks create dhan-cas-network --subnet-mode=custom
fi
if ! gc compute networks subnets describe dhan-cas-mumbai --region="$REGION" >/dev/null 2>&1; then
  gc compute networks subnets create dhan-cas-mumbai --network=dhan-cas-network --range=10.81.0.0/24 --region="$REGION"
fi
if ! gc compute firewall-rules describe dhan-cas-allow-iap-ssh >/dev/null 2>&1; then
  gc compute firewall-rules create dhan-cas-allow-iap-ssh --network=dhan-cas-network --direction=INGRESS --action=ALLOW --rules=tcp:22 --source-ranges=35.235.240.0/20 --target-tags=dhan-cas
fi
if ! gc compute addresses describe "$ADDRESS" --region="$REGION" >/dev/null 2>&1; then
  gc compute addresses create "$ADDRESS" --region="$REGION" --network-tier=PREMIUM
fi
if ! gc compute instances describe "$INSTANCE" --zone="$ZONE" >/dev/null 2>&1; then
  gc compute instances create "$INSTANCE" --zone="$ZONE" --machine-type=e2-small \
    --subnet=dhan-cas-mumbai --address="$ADDRESS" --network-tier=PREMIUM \
    --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB --boot-disk-type=pd-balanced --tags=dhan-cas \
    --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE \
    --no-service-account --no-scopes --shielded-secure-boot \
    --labels=app=dhan-cas,environment=commissioning
fi
gc compute addresses describe "$ADDRESS" --region="$REGION" --format='value(address)'
