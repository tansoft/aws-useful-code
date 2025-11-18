#!/bin/bash
# "Usage: ./delete_cognito_s2s.sh <name>"
PROJECT=${1:-"base-auth"}

echo "Cleaning up Cognito S2S resources for ${PROJECT}..."
CURPATHCURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)
source "${CURPATHCURPATH}/../.${PROJECT}-cognito-s2s.txt"
aws cognito-idp delete-user-pool-domain --domain $DOMAIN_PREFIX --user-pool-id $POOL_ID --region $REGION --no-cli-pager
sleep 2
aws cognito-idp delete-user-pool --user-pool-id $POOL_ID --region $REGION --no-cli-pager
echo "Resources deleted，Delete configure file .${PROJECT}-cognito-s2s.txt(yes/no)?"

read suredelete
if [ "$suredelete" == "yes" ]; then
    rm -f "${CURPATHCURPATH}/../.${PROJECT}-cognito-s2s.txt"
fi