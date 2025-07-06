# Flow-LiteLLM Integration

A specialized proxy server integrating [LiteLLM](https://github.com/BerriAI/litellm) with CI&T's Flow API orchestration platform for Gen AI. This integration enables seamless communication between client applications and multiple LLM providers through a unified interface.

## Overview

This project creates a proxy server that:

1. Integrates LiteLLM with Flow API for AI model orchestration
2. Handles authentication and token management with the Flow API service
3. Transforms requests according to specific LLM provider requirements
4. Supports multiple LLM providers (OpenAI, Google Gemini, AWS Bedrock/Claude, DeepSeek)
5. Provides model aliasing and routing capabilities

## Key Features

- **Unified LLM Access**: Interact with multiple LLM providers through a single API
- **Authentication Management**: Thread-safe token caching with automatic refresh
- **Request Transformation**: Custom handling for each LLM provider's specific requirements
- **Streaming Support**: Full support for streaming responses from compatible models
- **Docker Containerization**: Easy deployment with Docker and Nginx reverse proxy
- **Model Aliasing**: Route requests to specific models using aliases

## Architecture

The system consists of:

1. **LiteLLM Proxy**: Core service handling model routing and request/response processing
2. **Nginx Reverse Proxy**: URL pattern parsing for tenant/client info and header management
3. **Custom Callback Handler**: Authentication and request preprocessing
4. **Custom Patches**: Fixes for specific provider issues (like Anthropic/Claude)

## URL Handling and the '#' Character

A key technical feature of this integration is the strategic use of `#` characters at the end of API endpoints:

```python
data['api_base'] = "https://flow.ciandt.com/ai-orchestration-api/v1/foundry/chat/completions#"
```

This technique prevents LiteLLM from concatenating additional path components to the URLs. Without this approach, LiteLLM would automatically append model-specific paths to the base URL, which would make the URL invalid for the Flow API service.

For example:
- Without `#`: `https://flow.ciandt.com/ai-orchestration-api/v1/bedrock/invoke/anthropic.claude-3-sonnet` (invalid)
- With `#`: `https://flow.ciandt.com/ai-orchestration-api/v1/bedrock/invoke#` (correctly preserved)

## Supported Models

- **OpenAI**: GPT-4o, GPT-4o-mini, o3-mini
- **Google**: Gemini-2.0-flash, Gemini-2.5-pro
- **AWS Bedrock**: Claude-3-sonnet, Claude-35-sonnet, Claude-37-sonnet
- **DeepSeek**: DeepSeek-R1

## Setup Requirements

### Prerequisites

- Docker and docker-compose
- Access to the Flow API service
- Flow API credentials (client ID, client secret, and tenant)

### Configuration

Credentials can be provided in two ways:

1. **Environment Variables**:
   - `FLOW_CLIENT_ID`
   - `FLOW_CLIENT_SECRET`
   - `FLOW_TENANT`

2. **HTTP Headers**:
   - `FLOW_CLIENT_ID`
   - `FLOW_CLIENT_SECRET`
   - `FLOW_TENANT`

The Nginx reverse proxy also supports extracting credentials from the URL path pattern:
```
/[tenant]/[client_id]/v1/...
```

### Deployment

1. Clone the repository
2. Configure credentials as environment variables or prepare to pass them via headers
3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Usage

Once deployed, you can send requests to the proxy using standard LLM API formats:

```bash
# Using the URL path pattern for credentials
curl -X POST http://localhost:10000/my-tenant/my-client-id/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: my-client-secret" \
  -d '{
    "model": "bedrock/anthropic.claude-37-sonnet",
    "messages": [{"role": "user", "content": "Hello, world!"}]
  }'
```

## Live server

Today the server is available at:
https://flow-litellm.onrender.com/{tentant}/{clientId}
And expects an Authorization header with Bearer {clientSecret}

## Integration tools

- Cline / Roo / Continue:
  
  As Api Provider select LiteLLM, on base URL choose https://flow-litellm.onrender.com/{tentant}/{clientId}/ and as API Key set {clientSecret}

- Codex:

  Under ~/.codex/config.json set
  ```json
   {
      "model": "bedrock/anthropic.claude-37-sonnet",
      "provider": "flow",
      "providers": {
         "flow": {
            "name": "Flow",
            "baseURL": "https://flow-litellm.onrender.com/{tentant}/{clientId}/v1",
            "envKey": "{clientSecret}"
         }
      },
      "disableResponseStorage": false,
      "flexMode": false,
      "reasoningEffort": "high",
      "history": {
         "maxSize": 1000,
         "saveHistory": true,
         "sensitivePatterns": []
      },
      "tools": {
         "shell": {
            "maxBytes": 10240,
            "maxLines": 256
         }
      }
   }
  ```

- Claude Code:

  Under ~/.claude/settings.json
  ```json
  {
   "env": {
         "ANTHROPIC_AUTH_TOKEN": "{clientSecret}",
         "ANTHROPIC_BASE_URL": "https://flow-litellm.onrender.com/{tentant}/{clientId}/",
         "ANTHROPIC_MODEL": "bedrock/anthropic.claude-37-sonnet",
         "ANTHROPIC_SMALL_FAST_MODEL": "bedrock/anthropic.claude-37-sonnet"
      }
   }
  ```


## Custom Modifications

This integration includes several custom modifications:

1. **URL Handling**: The `#` character technique to prevent URL path concatenation
2. **Token Caching**: Thread-safe caching with TTL for Flow API tokens
3. **Request Transformations**: Custom handling for each LLM provider
4. **Empty Content Handling**: Special handling for empty content in Claude models
5. **Metadata Removal**: Removal of metadata fields that may cause issues with Claude models

## Technical Implementation Details

### Custom Callbacks

The `MyCustomHandler` class is responsible for:
- Token management with thread-safe caching
- Request preprocessing for different LLM providers
- Adding necessary headers and authentication tokens

### Anthropic/Claude Patches

Custom patches fix issues with Claude models:
- Removing metadata fields that cause problems
- Custom clientside credential handling for model groups
- Special handling for empty content

The main object of the monkey patches are to:
- Allow the system to continue if no model_group is resolved
- Remove the metadata object from the request body to flow (which seems required by LiteLLM) so we leave it on the body but we remove it just before sending it to flow orchestrator

## License

This project is available under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [LiteLLM](https://github.com/BerriAI/litellm) for the excellent LLM proxy library
- CI&T Flow API team for the orchestration platform
- Special thanks to Wellington Alves Rosa, with his initial work on [Cline - LiteLLM - Flow extension](https://flowlabs.ciandt.com/en-US/projects/extensions/cline-litellm-flow) which started this whole thing