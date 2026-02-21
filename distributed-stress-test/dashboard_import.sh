#!/bin/bash

region=us-east-1

DASHBOARD_NAME=$(jq -r '.DashboardName' dashboard_ddb.json)
DASHBOARD_BODY=$(jq -r '.DashboardBody' dashboard_ddb.json)
DASHBOARD_BODY="${DASHBOARD_BODY//us-east-1/${region}}"

aws cloudwatch put-dashboard \
    --dashboard-name "$DASHBOARD_NAME" \
    --dashboard-body "$DASHBOARD_BODY" \
    --region ${region}
