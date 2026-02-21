#!/bin/bash

region=us-east-1
dashboard=ddb-street-test

aws cloudwatch get-dashboard --dashboard-name ${dashboard} --region ${region} --output json | jq 'del(.DashboardArn)' > dashboard_ddb.json
