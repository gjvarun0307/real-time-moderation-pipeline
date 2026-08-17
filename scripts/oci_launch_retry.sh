#!/usr/bin/env bash
# Retries `oci compute instance launch` across all three Chicago ADs until
# Ampere A1 capacity frees up. Stops immediately on any non-capacity error
# instead of retrying forever on a real config mistake.
set -euo pipefail

COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaj6rima6qtwn4ei6ubkatzfwv3ozr4yszxctg3cwnrohfbgh6yxdq"
SUBNET_ID="ocid1.subnet.oc1.us-chicago-1.aaaaaaaazv27masozggmtuqizs6dije37bvxom3tyv7qlsxghtjvsc6qhz2q"
IMAGE_ID="ocid1.image.oc1.us-chicago-1.aaaaaaaav6lpo75wu2aw7w7evsin5xfrh76nc4rnqpkmup6jbb53bxv4nhgq" # Canonical-Ubuntu-24.04-Minimal-aarch64-2026.07.17-0
SSH_KEY_PATH="$HOME/.ssh/oci_moderation_pipeline.pub"
DISPLAY_NAME="moderation-pipeline-node"
SHAPE="VM.Standard.A1.Flex"
OCPUS=2
MEMORY_GB=12

ADS=(
  "ofNU:US-CHICAGO-1-AD-1"
  "ofNU:US-CHICAGO-1-AD-2"
  "ofNU:US-CHICAGO-1-AD-3"
)

SLEEP_BASE=45    # seconds between full AD cycles
SLEEP_JITTER=30  # random 0-30s added on top, avoids a fixed-interval hammering pattern
LOG_FILE="$(dirname "$0")/data/oci_launch_retry.log"

attempt=0
while true; do
  for ad in "${ADS[@]}"; do
    attempt=$((attempt + 1))
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$ts] attempt $attempt: $ad" | tee -a "$LOG_FILE"

    set +e
    output=$(oci compute instance launch \
      --compartment-id "$COMPARTMENT_ID" \
      --availability-domain "$ad" \
      --shape "$SHAPE" \
      --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_GB}" \
      --image-id "$IMAGE_ID" \
      --subnet-id "$SUBNET_ID" \
      --assign-public-ip true \
      --ssh-authorized-keys-file "$SSH_KEY_PATH" \
      --display-name "$DISPLAY_NAME" \
      2>&1)
    status=$?
    set -e

    if [ "$status" -eq 0 ]; then
      echo "[$ts] LAUNCHED on $ad" | tee -a "$LOG_FILE"
      echo "$output" | tee -a "$LOG_FILE"
      exit 0
    fi

    if echo "$output" | grep -qi "capacity"; then
      echo "[$ts] out of capacity on $ad, will retry" | tee -a "$LOG_FILE"
    else
      echo "[$ts] non-capacity error, stopping:" | tee -a "$LOG_FILE"
      echo "$output" | tee -a "$LOG_FILE"
      exit 1
    fi
  done

  sleep_time=$((SLEEP_BASE + RANDOM % SLEEP_JITTER))
  echo "sleeping ${sleep_time}s before next cycle..." | tee -a "$LOG_FILE"
  sleep "$sleep_time"
done
