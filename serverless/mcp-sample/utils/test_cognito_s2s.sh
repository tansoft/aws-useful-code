#!/bin/bash
# "Usage: ./test_cognito_s2s.sh <name>"
PROJECT=${1:-"base-auth"}

echo "Retrieving access token for ${PROJECT}..."
CURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)
source "${CURPATH}/../.${PROJECT}-cognito-s2s.txt"
TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "${CLIENT_ID}:${CLIENT_SECRET}" \
  -d "grant_type=client_credentials&scope=${SCOPES}")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')

if [ "$ACCESS_TOKEN" != "null" ]; then
  echo ""
  echo "Access Token:"
  echo $ACCESS_TOKEN
  echo ""
  echo "Token payload:"
  echo $ACCESS_TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | jq .
else
  echo "✗ Failed to obtain token"
  echo $TOKEN_RESPONSE | jq
fi
