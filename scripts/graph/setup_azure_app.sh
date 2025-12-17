#!/bin/bash
# Azure CLI Setup Script for Microsoft Graph App Registration
# This script automates the creation of an Azure AD app registration with proper Graph API permissions

set -e  # Exit on any error

# Configuration
APP_NAME="Local-AI-Assistant-Graph"
REDIRECT_URI="http://localhost:8000/auth/graph/callback"
GRAPH_API_ID="00000003-0000-0000-c000-000000000000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Microsoft Graph App Registration Setup ===${NC}"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI is not installed${NC}"
    echo "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login to Azure
echo -e "${YELLOW}Step 1: Logging in to Azure...${NC}"
az login

# Get tenant ID
TENANT_ID=$(az account show --query tenantId -o tsv)
echo -e "${GREEN}✓ Logged in to tenant: ${TENANT_ID}${NC}"
echo ""

# Create app registration
echo -e "${YELLOW}Step 2: Creating app registration '${APP_NAME}'...${NC}"
APP_RESPONSE=$(az ad app create \
    --display-name "${APP_NAME}" \
    --sign-in-audience AzureADMyOrg \
    --web-redirect-uris "${REDIRECT_URI}" \
    --enable-access-token-issuance true \
    --enable-id-token-issuance true)

APP_ID=$(echo "${APP_RESPONSE}" | jq -r '.appId')
OBJECT_ID=$(echo "${APP_RESPONSE}" | jq -r '.id')

echo -e "${GREEN}✓ App created with ID: ${APP_ID}${NC}"
echo ""

# Get Microsoft Graph Service Principal
echo -e "${YELLOW}Step 3: Retrieving Microsoft Graph permissions...${NC}"
GRAPH_SP=$(az ad sp show --id ${GRAPH_API_ID})

# Extract permission IDs for Microsoft Graph
# Delegated permissions (oauth2PermissionScopes)
TASKS_READWRITE_ID=$(echo "${GRAPH_SP}" | jq -r '.oauth2PermissionScopes[] | select(.value=="Tasks.ReadWrite") | .id')
TASKS_READWRITE_ALL_ID=$(echo "${GRAPH_SP}" | jq -r '.oauth2PermissionScopes[] | select(.value=="Tasks.ReadWrite.All") | .id')
GROUP_READ_ALL_ID=$(echo "${GRAPH_SP}" | jq -r '.oauth2PermissionScopes[] | select(.value=="Group.Read.All") | .id')
USER_READ_ID=$(echo "${GRAPH_SP}" | jq -r '.oauth2PermissionScopes[] | select(.value=="User.Read") | .id')

# Application permissions (appRoles) - for daemon/service scenarios
TASKS_READWRITE_APP_ID=$(echo "${GRAPH_SP}" | jq -r '.appRoles[] | select(.value=="Tasks.ReadWrite.All") | .id')
GROUP_READ_APP_ID=$(echo "${GRAPH_SP}" | jq -r '.appRoles[] | select(.value=="Group.Read.All") | .id')

echo -e "${GREEN}✓ Retrieved permission IDs${NC}"
echo ""

# Add delegated permissions (for user context)
echo -e "${YELLOW}Step 4: Adding delegated permissions...${NC}"
az ad app permission add \
    --id ${APP_ID} \
    --api ${GRAPH_API_ID} \
    --api-permissions \
        ${TASKS_READWRITE_ID}=Scope \
        ${TASKS_READWRITE_ALL_ID}=Scope \
        ${GROUP_READ_ALL_ID}=Scope \
        ${USER_READ_ID}=Scope

echo -e "${GREEN}✓ Delegated permissions added:${NC}"
echo "  - Tasks.ReadWrite (access user's tasks)"
echo "  - Tasks.ReadWrite.All (access all tasks user can see)"
echo "  - Group.Read.All (read Planner plans in groups)"
echo "  - User.Read (sign in and read user profile)"
echo ""

# Add application permissions (for service/daemon scenarios)
echo -e "${YELLOW}Step 5: Adding application permissions...${NC}"
az ad app permission add \
    --id ${APP_ID} \
    --api ${GRAPH_API_ID} \
    --api-permissions \
        ${TASKS_READWRITE_APP_ID}=Role \
        ${GROUP_READ_APP_ID}=Role

echo -e "${GREEN}✓ Application permissions added:${NC}"
echo "  - Tasks.ReadWrite.All (app-only access)"
echo "  - Group.Read.All (app-only access)"
echo ""

# Grant admin consent
echo -e "${YELLOW}Step 6: Granting admin consent...${NC}"
echo -e "${YELLOW}Note: This requires Global Administrator or Application Administrator role${NC}"

if az ad app permission admin-consent --id ${APP_ID} 2>/dev/null; then
    echo -e "${GREEN}✓ Admin consent granted${NC}"
else
    echo -e "${YELLOW}⚠ Could not auto-grant admin consent${NC}"
    echo -e "${YELLOW}Manual action required:${NC}"
    echo "  1. Go to Azure Portal: https://portal.azure.com"
    echo "  2. Navigate to Azure Active Directory > App registrations"
    echo "  3. Find '${APP_NAME}' and click on it"
    echo "  4. Go to 'API permissions' and click 'Grant admin consent'"
fi
echo ""

# Create client secret
echo -e "${YELLOW}Step 7: Creating client secret...${NC}"
SECRET_RESPONSE=$(az ad app credential reset \
    --id ${APP_ID} \
    --append \
    --display-name "LocalAssistant-Secret-$(date +%Y%m%d)" \
    --years 2)

CLIENT_SECRET=$(echo "${SECRET_RESPONSE}" | jq -r '.password')
echo -e "${GREEN}✓ Client secret created (valid for 2 years)${NC}"
echo ""

# Output environment variables
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo ""
echo -e "${YELLOW}Add these to your .env file:${NC}"
echo ""
echo "# Microsoft Graph Configuration"
echo "GRAPH_TENANT_ID=\"${TENANT_ID}\""
echo "GRAPH_CLIENT_ID=\"${APP_ID}\""
echo "GRAPH_CLIENT_SECRET=\"${CLIENT_SECRET}\""
echo "GRAPH_REDIRECT_URI=\"${REDIRECT_URI}\""
echo ""

# Save to file
ENV_FILE="/Users/andrew/Projects/AGENTS/local_assistant/.env.graph"
cat > "${ENV_FILE}" << EOL
# Microsoft Graph Configuration
# Generated: $(date)
GRAPH_TENANT_ID="${TENANT_ID}"
GRAPH_CLIENT_ID="${APP_ID}"
GRAPH_CLIENT_SECRET="${CLIENT_SECRET}"
GRAPH_REDIRECT_URI="${REDIRECT_URI}"

# Authority URL (for MSAL)
GRAPH_AUTHORITY="https://login.microsoftonline.com/${TENANT_ID}"

# Scopes (space-separated)
GRAPH_SCOPES="Tasks.ReadWrite Tasks.ReadWrite.All Group.Read.All User.Read offline_access"
EOL

echo -e "${GREEN}✓ Configuration saved to: ${ENV_FILE}${NC}"
echo ""

echo -e "${YELLOW}Next steps:${NC}"
echo "1. Copy contents of ${ENV_FILE} to your main .env file"
echo "2. If admin consent failed, manually grant it in Azure Portal"
echo "3. Run: uv sync  (to install Microsoft Graph dependencies)"
echo "4. Test authentication: python3 scripts/graph/test_auth.py"
echo ""

echo -e "${GREEN}=== App Registration Details ===${NC}"
echo "App Name:        ${APP_NAME}"
echo "Application ID:  ${APP_ID}"
echo "Tenant ID:       ${TENANT_ID}"
echo "Redirect URI:    ${REDIRECT_URI}"
echo ""

# Additional info
echo -e "${YELLOW}Important Notes:${NC}"
echo "- Client secret expires in 2 years (on $(date -v+2y '+%Y-%m-%d' 2>/dev/null || date -d '+2 years' '+%Y-%m-%d'))"
echo "- Store CLIENT_SECRET securely (it's shown only once)"
echo "- For production, use Azure Key Vault or environment-specific secrets"
echo "- Delegated permissions require user interaction (OAuth flow)"
echo "- Application permissions require admin consent and work without user"
echo ""

echo -e "${GREEN}Setup script completed successfully!${NC}"
