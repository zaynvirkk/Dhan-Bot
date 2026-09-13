#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?usage: create_gcp_vm.sh PROJECT_ID}"
REGION="${GCP_REGION:-asia-south1}"
ZONE="${GCP_ZONE:-asia-south1-a}"
INSTANCE="${GCP_INSTANCE:-sablestone-dhan-cas}"
ADDRESS="${GCP_ADDRESS:-sablestone-dhan-cas-ip}"

echo "This script only prints the reviewed commands. It never creates cloud resources."
cat <<EOF
gcloud config set project ${PROJECT_ID}
gcloud compute addresses create ${ADDRESS} --region ${REGION}
gcloud compute instances create ${INSTANCE} --zone ${ZONE} --machine-type e2-micro --address ${ADDRESS} --network-tier PREMIUM --metadata enable-oslogin=TRUE
EOF
echo "Review, reserve the final static IP, whitelist it at Dhan, and run the commands explicitly."
