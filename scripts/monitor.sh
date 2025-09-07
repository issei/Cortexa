#!/bin/bash
set -e

# Parse command line arguments
DURATION="5m"
THRESHOLD="1.0"

while [[ $# -gt 0 ]]; do
  case $1 in
    --duration)
      DURATION="$2"
      shift 2
      ;;
    --threshold)
      THRESHOLD="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Convert duration to seconds
duration_seconds=$(echo "$DURATION" | sed 's/m/*60/;s/h/*3600/;s/d/*86400/' | bc)
end_time=$((SECONDS + duration_seconds))

echo "Starting monitoring for $DURATION (threshold: $THRESHOLD%)"

while [ $SECONDS -lt $end_time ]; do
  # Get error rate from CloudWatch
  error_rate=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value="${FUNCTION_NAME}" \
    --start-time $(date -u -d '5 minutes ago' "+%Y-%m-%dT%H:%M:%SZ") \
    --end-time $(date -u "+%Y-%m-%dT%H:%M:%SZ") \
    --period 300 \
    --statistics Sum \
    --query "Datapoints[0].Sum" \
    --output text)

  # If error_rate is empty or null, set it to 0
  if [ -z "$error_rate" ] || [ "$error_rate" == "None" ]; then
    error_rate=0
  fi

  if (( $(echo "$error_rate > $THRESHOLD" | bc -l) )); then
    echo "Error rate ($error_rate) exceeds threshold ($THRESHOLD%)"
    exit 1
  fi

  sleep 60
done

echo "Monitoring completed successfully"
