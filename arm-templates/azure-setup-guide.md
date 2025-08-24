# Azure Setup Guide for PokePal

This guide helps you set up the required Azure resources for the PokePal project.

## Required Azure Resources

### 1. Azure IoT Hub
- **Purpose**: Device management and message routing
- **SKU**: F1 (Free) for development, S1 for production
- **Configuration**:
  - Enable Module Twin for configuration management
  - Set up routing rules for telemetry data
  - Create consumer groups for Function Apps

### 2. Azure Container Registry (ACR)
- **Purpose**: Docker image repository for IoT Edge modules
- **SKU**: Basic tier
- **Configuration**:
  - Enable Admin user for initial setup only (disable for production)
  - Use RBAC with Service Principal for production
  - Consider Private Endpoints for enhanced security
  - Note the login server and credentials

### 3. Azure Cosmos DB
- **Purpose**: Store conversation logs and memory data
- **API**: Core (SQL)
- **Configuration**:
  - Create database: `pokepal-db` (or your preferred name)
  - Create containers:
    - `conversations`: For conversation logs
    - `memories`: For generated memory summaries
  - Partition keys:
    - `/deviceId` for conversations
    - `/deviceId` for memories

### 4. Azure Storage Account
- **Purpose**: Store audio files and temporary data
- **Configuration**:
  - Create containers:
    - `audio-files`: For audio recordings
    - `memory-files`: For memory JSON files
    - `azure-webjobs-secrets`: For Functions runtime
  - Enable blob versioning for data protection
  - **Security**: Disable shared key access for production (use Azure AD only)
  - Set network ACLs default action to "Deny" and allow specific IPs/VNets

### 5. Azure Key Vault
- **Purpose**: Secure storage for API keys and secrets
- **Secrets to store**:
  - `openai-api-key`: Your OpenAI API key
  - `azure-speech-key`: Azure Cognitive Services Speech key
  - `cosmos-connection-string`: Cosmos DB connection string
  - `storage-connection-string`: Storage account connection string
  - `pokepal-acr-password`: ACR admin password (if admin user is enabled)
- **Security**: 
  - Set network ACLs default to "Deny" and allow specific IPs/VNets
  - Use RBAC authorization instead of access policies
  - Consider Private Endpoints for production

### 6. Azure Cognitive Services - Speech
- **Purpose**: Text-to-Speech synthesis
- **SKU**: F0 (Free) for testing, S0 for production
- **Region**: Japan East recommended

### 7. Azure Functions
- **Purpose**: Process telemetry and generate memory files
- **Runtime**: Python 3.11
- **Functions needed**:
  - `ConversationLogger`: Event Hub triggered, logs to Cosmos DB
  - `MemoryGenerator`: Timer triggered (hourly), generates memory summaries

## Setup Order

1. **Resource Group**: Create a resource group in Japan East region
2. **Storage Account**: Create first (needed by other services)
3. **Cosmos DB**: Create database and containers
4. **Key Vault**: Create and add secrets
5. **IoT Hub**: Create and configure routing
6. **Container Registry**: Create and enable admin user
7. **Cognitive Services**: Create Speech service
8. **Azure Functions**: Deploy after all dependencies are ready

## Environment Variables

For local development, create a `.env` file:

```bash
# Azure IoT Hub
IOT_HUB_CONNECTION_STRING="your-iot-hub-connection-string"
DEVICE_CONNECTION_STRING="your-device-connection-string"

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING="your-storage-connection-string"

# Azure Cosmos DB
COSMOS_ENDPOINT="https://your-cosmos.documents.azure.com:443/"
COSMOS_KEY="your-cosmos-key"

# Azure Key Vault
KEY_VAULT_URL="https://your-keyvault.vault.azure.net/"

# OpenAI
OPENAI_API_KEY="your-openai-api-key"

# Azure Speech
AZURE_SPEECH_KEY="your-speech-key"
AZURE_SPEECH_REGION="japaneast"
```

## Deployment Configuration

### IoT Edge Deployment Manifest

Key settings for `deployment.template.json`:

```json
{
  "modulesContent": {
    "$edgeAgent": {
      "properties.desired": {
        "runtime": {
          "settings": {
            "registryCredentials": {
              "YOUR_ACR": {
                "address": "your-acr.azurecr.io",
                "username": "your-acr-username",
                "password": "${ACR_PASSWORD}"
              }
            }
          }
        }
      }
    }
  }
}
```

### Module Twin Configuration

Example Module Twin desired properties:

```json
{
  "properties": {
    "desired": {
      "audio": {
        "sample_rate": 16000,
        "channels": 1
      },
      "conversation": {
        "no_voice_sleep_threshold": 300,
        "farewell_message": "Thank you for talking with me"
      },
      "llm": {
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 500
      }
    }
  }
}
```

## Security Best Practices

### Development Environment
1. **Never commit secrets** to version control
2. **Use Key Vault** for all sensitive configuration
3. **Enable RBAC** on all Azure resources
4. **Monitor resource usage** and set up alerts

### Production Hardening
1. **Network Security**:
   - Use Private Endpoints for all services
   - Set network ACLs default to "Deny"
   - Configure IP restrictions for Function Apps
   - Disable public network access where possible

2. **Authentication**:
   - Disable local/key-based authentication (`disableLocalAuth: true`)
   - Use Azure AD authentication exclusively
   - Disable admin users on ACR
   - Disable shared key access on Storage Accounts

3. **Access Control**:
   - Use RBAC instead of access policies
   - Apply principle of least privilege
   - Disable FTP/Basic publishing credentials
   - Rotate keys and secrets regularly

4. **Encryption**:
   - Ensure HTTPS only (`httpsOnly: true`)
   - Use TLS 1.2 minimum
   - Enable encryption at rest for all services

## Cost Optimization

- Use **Free tier** services during development
- Set up **spending alerts** in Azure Cost Management
- Consider **Reserved Instances** for production
- Clean up unused resources regularly

## ARM Template Usage

The included `resource-group-template.json` provides a complete infrastructure definition. 

### Important Notes:
- This is a **sample template** optimized for ease of deployment
- Contains **placeholder values** (YOUR_*) that must be replaced
- Uses **development-friendly defaults** (public access enabled)
- For production, apply the security hardening recommendations above

### Deployment:
```bash
# Create parameter file (do not commit!)
cp parameters.example.json parameters.json
# Edit parameters.json with your values

# Deploy template
az deployment group create \
  --resource-group YOUR_RESOURCE_GROUP \
  --template-file resource-group-template.json \
  --parameters @parameters.json
```

### .gitignore Recommendations:
```
*.parameters.json
*.bicepparam
local.settings.json
.env
```

## Support

For detailed ARM templates or infrastructure-as-code examples, please contact the project maintainers.