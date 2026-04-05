#!/bin/bash
# "Usage: ./delete_cognito_s2s.sh <name>"
PROJECT=${1:-"base-auth"}

echo "Cleaning up Cognito S2S resources for ${PROJECT}..."
CURPATHCURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)
source "${CURPATHCURPATH}/../.${PROJECT}-config.txt"
aws cognito-idp delete-user-pool-domain --domain $DOMAIN_PREFIX --user-pool-id $POOL_ID --region $REGION --no-cli-pager
sleep 2
aws cognito-idp delete-user-pool --user-pool-id $POOL_ID --region $REGION --no-cli-pager
echo 

read -p "Resources deleted，Delete configure file .${PROJECT}-config.txt (y/n)?" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    rm -f "${CURPATHCURPATH}/../.${PROJECT}-config.txt"
fi