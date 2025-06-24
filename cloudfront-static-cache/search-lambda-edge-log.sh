#!/bin/bash
# ./search-lambda-edge-log.sh us-east-1.static-cache-for-open-street-map-edge

# Colors for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# List of regions where Lambda@Edge can be executed
REGIONS=(
    "us-east-1"
    "us-east-2"
    "us-west-1"
    "us-west-2"
    "ap-south-1"
    "ap-northeast-2"
    "ap-southeast-1"
    "ap-southeast-2"
    "ap-northeast-1"
    "eu-central-1"
    "eu-west-1"
    "eu-west-2"
    "sa-east-1"
)

# Function name as argument
if [ -z "$1" ]; then
    echo -e "${RED}Please provide the Lambda function name as an argument${NC}"
    echo "Usage: $0 <function-name>"
    exit 1
fi

FUNCTION_NAME=$1
MINUTES=${2:-60} # Default to last 60 minutes if not specified

echo -e "${GREEN}Searching for Lambda@Edge logs for function: ${YELLOW}$FUNCTION_NAME${NC}"
echo -e "${GREEN}Looking at last ${YELLOW}$MINUTES${GREEN} minutes${NC}"
echo "----------------------------------------"

for region in "${REGIONS[@]}"; do
    echo -e "${GREEN}Checking region: ${YELLOW}$region${NC}"
    
    # Get log group name
    LOG_GROUP="/aws/lambda/$FUNCTION_NAME"
    
    # Check if log group exists in this region
    if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region "$region" --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "^$LOG_GROUP"; then
        echo -e "${GREEN}Found log group in $region${NC}"
        
        # Get timestamp for X minutes ago
        TIMESTAMP=$(($(date +%s) - MINUTES * 60))
        TIMESTAMP_MS=$((TIMESTAMP * 1000))
        
        # Get the most recent log streams
        STREAMS=$(aws logs describe-log-streams \
            --log-group-name "$LOG_GROUP" \
            --region "$region" \
            --order-by LastEventTime \
            --descending \
            --max-items 5 \
            --query 'logStreams[?lastEventTimestamp > `'$TIMESTAMP_MS'`].logStreamName' \
            --output text)
        
        if [ ! -z "$STREAMS" ]; then
            for stream in $STREAMS; do
                echo -e "\n${YELLOW}Log stream: $stream${NC}"
                # Get logs from this stream
                aws logs get-log-events \
                    --log-group-name "$LOG_GROUP" \
                    --log-stream-name "$stream" \
                    --region "$region" \
                    --start-time $TIMESTAMP_MS \
                    --query 'events[].message' \
                    --output text
            done
        else
            echo "No recent log streams found in this region"
        fi
    else
        echo "No log group found in this region"
    fi
    echo "----------------------------------------"
done
