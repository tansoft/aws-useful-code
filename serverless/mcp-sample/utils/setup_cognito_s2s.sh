#!/bin/bash
# "Usage: ./setup_cognito_s2s.sh <region> <name>"
REGION=${1:-"us-east-1"}
PROJECT=${2:-"base-auth"}

CURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)

echo "================================================"
echo "Setting up ${PROJECT} Cognito S2S Authentication"
echo "Region: $REGION"
echo "================================================"

# 1. 创建 User Pool
echo ""
echo "[1/5] Creating User Pool..."
POOL_RESPONSE=$(aws cognito-idp create-user-pool \
  --pool-name "${PROJECT}" \
  --region $REGION \
  --no-cli-pager)
POOL_ID=$(echo $POOL_RESPONSE | jq -r '.UserPool.Id')
echo "✓ User Pool ID: $POOL_ID"

# 2. 创建 Domain
echo ""
echo "[2/5] Creating Domain..."
DOMAIN_PREFIX="${PROJECT}-$(date +%s)"
aws cognito-idp create-user-pool-domain \
  --domain "${DOMAIN_PREFIX}" \
  --user-pool-id $POOL_ID \
  --region $REGION \
  --no-cli-pager
TOKEN_ENDPOINT="https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com/oauth2/token"
echo "✓ Token URL: $TOKEN_ENDPOINT"

# 3. 创建 Resource Server
echo ""
echo "[3/5] Creating Resource Server..."
RESOURCE_SERVER_IDENTIFIER="${PROJECT}-api"
aws cognito-idp create-resource-server \
  --user-pool-id $POOL_ID \
  --identifier $RESOURCE_SERVER_IDENTIFIER \
  --name "${PROJECT} API" \
  --scopes \
    ScopeName=read,ScopeDescription="Read access" \
    ScopeName=write,ScopeDescription="Write access" \
  --region $REGION \
  --no-cli-pager
echo "✓ Resource Server: $RESOURCE_SERVER_IDENTIFIER"

# 4. 创建 App Client (Service-to-Service)
echo ""
echo "[4/5] Creating App Client for Service-to-Service Auth..."
CLIENT_RESPONSE=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "${PROJECT}Client" \
  --generate-secret \
  --allowed-o-auth-flows "client_credentials" \
  --allowed-o-auth-scopes \
    "${RESOURCE_SERVER_IDENTIFIER}/read" \
    "${RESOURCE_SERVER_IDENTIFIER}/write" \
  --allowed-o-auth-flows-user-pool-client \
  --region $REGION \
  --no-cli-pager)
CLIENT_ID=$(echo $CLIENT_RESPONSE | jq -r '.UserPoolClient.ClientId')
CLIENT_SECRET=$(echo $CLIENT_RESPONSE | jq -r '.UserPoolClient.ClientSecret')
echo "✓ Client ID: $CLIENT_ID"
echo "✓ Client Secret: $CLIENT_SECRET"

# 5. 测试获取 Token
echo ""
echo "[5/5] Testing token retrieval..."
TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "${CLIENT_ID}:${CLIENT_SECRET}" \
  -d "grant_type=client_credentials&scope=${RESOURCE_SERVER_IDENTIFIER}/read ${RESOURCE_SERVER_IDENTIFIER}/write")
ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')

if [ "$ACCESS_TOKEN" != "null" ] && [ ! -z "$ACCESS_TOKEN" ]; then
  echo "✓ Token obtained successfully!"
  echo "Access Token (first 50 chars): ${ACCESS_TOKEN:0:50}..."
else
  echo "✗ Failed to obtain token"
  echo $TOKEN_RESPONSE | jq
fi

# 生成 Discovery URL
DISCOVERY_URL="https://cognito-idp.${REGION}.amazonaws.com/${POOL_ID}/.well-known/openid-configuration"

# 输出配置摘要
OUTPUT="
#================================================
# ${PROJECT} S2S Authentication Configuration
#================================================
# User Pool ID: $POOL_ID
# Region: $REGION
# Domain Prefix: $DOMAIN_PREFIX
# Token Endpoint: $TOKEN_ENDPOINT
# Discovery URL: $DISCOVERY_URL
# Resource Server: $RESOURCE_SERVER_IDENTIFIER
#
# App Client (Service-to-Service):
#  Client ID: $CLIENT_ID
#  Client Secret: $CLIENT_SECRET
#
# Scopes:
#  - ${RESOURCE_SERVER_IDENTIFIER}/read
#  - ${RESOURCE_SERVER_IDENTIFIER}/write
#================================================
"

# Output to console
echo "$OUTPUT"

# Write to file
cat > "${CURPATH}/../.${PROJECT}-cognito-s2s.txt" << EOFCONFIG
$OUTPUT
POOL_ID=$POOL_ID
REGION=$REGION
DOMAIN_PREFIX=$DOMAIN_PREFIX
TOKEN_ENDPOINT=$TOKEN_ENDPOINT
DISCOVERY_URL=$DISCOVERY_URL
RESOURCE_SERVER_IDENTIFIER=$RESOURCE_SERVER_IDENTIFIER
CLIENT_ID=$CLIENT_ID
CLIENT_SECRET=$CLIENT_SECRET
SCOPES="${RESOURCE_SERVER_IDENTIFIER}/read ${RESOURCE_SERVER_IDENTIFIER}/write"
ACCESS_TOKEN=$ACCESS_TOKEN
EOFCONFIG

echo ""
echo "✓ Configuration saved to .${PROJECT}-cognito-s2s.txt"

echo ""
echo "================================================"
echo "Setup complete! Use these files:"
echo "  cat .${PROJECT}-cognito-s2s.txt: Full configuration"
echo "  ./utils/test_cognito_s2s.sh ${PROJECT}: Test ${PROJECT} token retrieval"
echo "  ./utils/delete_cognito_s2s.sh ${PROJECT}: Delete ${PROJECT} resources"
echo "================================================"
