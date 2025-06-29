import json
import os
import traceback
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache, ProxyException
from typing import Literal
import time
import requests
import threading
from cachetools import TTLCache
from fastapi import HTTPException

# Import our custom Anthropic monkey patches
from anthropic_patches import apply_anthropic_patches

# Apply the monkey patches
apply_anthropic_patches()

class MyCustomHandler(CustomLogger):
    """
    Custom handler for Flow API integration with token caching.
    
    Features:
    - Thread-safe token caching with TTL
    - User-specific tokens using client secret as cache key
    - Automatic token refresh when expired
    - Support for multiple concurrent users with different credentials
    """
    # Class-level token cache with TTL (in seconds)
    # Using a TTL slightly shorter than the actual token expiration time
    _token_cache = TTLCache(maxsize=100, ttl=3500)  # TTL of 3500 seconds (58.3 minutes)
    _cache_lock = threading.RLock()  # Reentrant lock for thread safety
    
    def __init__(self):
        pass

    flow_agent = 'flow-api-proxy'
    
    # Track the current request data for header access
    current_request_data = None

    async def async_pre_call_hook(self, user_api_key_dict: UserAPIKeyAuth, cache: DualCache, data: dict, call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
        ]):

        # import json
        # print(json.dumps(data))
        
        # Store the current request data for header access
        self.current_request_data = data
        
        data = self.prepare_base_request(data)

        if 'openai' in data['model']:
            return self.prepare_openai(data)
        if 'bedrock' in data['model'] or 'claude' in data['model']:
            return self.prepare_bedrock(data)
        if 'gemini' in data['model']:
            return self.prepare_gemini(data)
        if 'deepseek' in data['model'].lower():
            return self.prepare_deepseek(data)
        else:
            return None

    def prepare_base_request(self, data):
        token = self.prepare_flow_token(data)
        _, _, tenant = self.get_credentials_from_headers(data)

        data['api_key'] = token if token else "ignore"
        #print(f"API Key: {data['api_key']}")
        data['extra_headers'] = {}
        data['extra_headers']['Authorization'] = f"Bearer {token}" if token else "Bearer ignore"
        data['extra_headers']['flowAgent'] = 'LiteLLM Proxy'
        data['extra_headers']['flowTenant'] = tenant

        return data

    def prepare_deepseek(self, data):
        data['api_base'] = "https://flow.ciandt.com/ai-orchestration-api/v1/foundry/chat/completions#"

        return data

    def prepare_gemini(self, data):
        if 'stream' in data and data['stream'] == True:
            data['api_base'] = "https://flow.ciandt.com/ai-orchestration-api/v1/google/streamGenerateContent#"
        else:
            data['api_base'] = "https://flow.ciandt.com/ai-orchestration-api/v1/google/generateContent#"

        return data

    def prepare_bedrock(self, data):
        os.environ["AWS_ACCESS_KEY_ID"] = "ignore"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "ignore"
        os.environ["AWS_REGION_NAME"] = "ignore"

        if 'stream' in data and data['stream'] == True:
            data['api_base'] = "https://flow.ciandt.com/ai-orchestration-api/v1/bedrock/invoke-with-response-stream#"
        else:
            data['api_base'] = "https://flow.ciandt.com/ai-orchestration-api/v1/bedrock/invoke#"

        # Map model aliases to their proper names
        if data['model'] == 'claude-3-7-sonnet-latest':
            data['model'] = 'bedrock/anthropic.claude-37-sonnet'
            
        data['allowedModels'] = ['anthropic.claude-37-sonnet']
        # Always set allowedModels to a list with the model name without the 'bedrock/' prefix
        if 'model' in data and data["model"]:
            model_name = data["model"]
            if model_name.startswith('bedrock/'):
                model_name = model_name.removeprefix('bedrock/')
            data['allowedModels'] = [model_name]
            # Ensure metadata exists and model_group is set
            if 'metadata' not in data:
                data['metadata'] = {}
            data['metadata']['model_group'] = 'amazon-bedrock'
            
            # For Anthropic models via Bedrock, we need to use the correct format
            # The model should be 'bedrock/anthropic.claude-3-sonnet' not just 'anthropic.claude-3-sonnet'
            # This ensures the model is properly recognized as a Bedrock model
            if not data["model"].startswith('bedrock/') and 'anthropic' in model_name:
                data["model"] = f"bedrock/{model_name}"

        # Set up provider_specific_header for Bedrock models
        if 'provider_specific_header' not in data:
            data['provider_specific_header'] = {}
        
        # For Anthropic models, we need to set the custom_llm_provider
        if 'claude' in data['model'].lower():
            data['provider_specific_header']['custom_llm_provider'] = 'anthropic'
        
        if 'v1/messages' in data['proxy_server_request']['url']:
            # Add our custom headers to provider_specific_header
            if 'extra_headers' not in data['provider_specific_header']:
                data['provider_specific_header']['extra_headers'] = {}
            
            # Get token from cache or generate a new one
            token = self.prepare_flow_token(data)
            _, _, tenant = self.get_credentials_from_headers(data)
            
            # Set our custom headers
            data['provider_specific_header']['extra_headers']['Authorization'] = f"Bearer {token}" if token else "Bearer ignore"
            data['provider_specific_header']['extra_headers']['flowAgent'] = 'LiteLLM Proxy'
            data['provider_specific_header']['extra_headers']['flowTenant'] = tenant

        if 'claude-35-sonnet' in data["model"] and 'parallel_tool_calls' in data:
            del data['parallel_tool_calls']

        for message in data['messages'] if 'messages' in data else []:
            if 'content' in message and type(message['content']) is str and message['content'].strip() == "":
                message['content'] = ":"

        return data

    def prepare_openai(self, data):
        data['api_base'] = "https://flow.ciandt.com/ai-orchestration-api/v1/openai/"

        return data

    def get_credentials_from_headers(self, data):
        """
        Extract Flow credentials from request headers if available.
        Returns a tuple of (client_id, client_secret, tenant)
        """
        client_id = None
        client_secret = None
        tenant = None

        
        # Check if we have current request data with headers
        if data and 'proxy_server_request' in data and 'headers' in data['proxy_server_request']:
            headers = data['proxy_server_request']['headers']
            # Check for Flow credentials in headers (case-insensitive)
            for header_name, header_value in headers.items():
                if header_name.upper() == 'FLOW_CLIENT_ID':
                    client_id = header_value
                elif header_name.upper() == 'FLOW_CLIENT_SECRET':
                    client_secret = header_value
                elif header_name.upper() == 'FLOW_TENANT':
                    tenant = header_value
        
        return client_id, client_secret, tenant

    def prepare_flow_token(self, data):
        """
        Get a token from cache or generate a new one using client credentials.
        Uses client_secret as the cache key for user-specific tokens.
        """
        token_url = 'https://flow.ciandt.com/auth-engine-api/v1/api-key/token'
        
        # First try to get credentials from headers
        header_client_id, header_client_secret, header_tenant = self.get_credentials_from_headers(data)

        # Use headers if available, otherwise fall back to environment variables
        client_id = header_client_id or os.getenv('FLOW_CLIENT_ID')
        client_secret = header_client_secret or os.getenv('FLOW_CLIENT_SECRET')
        tenant = header_tenant or os.getenv('FLOW_TENANT')
                
        # Return None if credentials are not configured
        if not client_id or not client_secret or not tenant:
            return None
            
        # Use client_secret as the cache key
        cache_key = f"{client_secret}:{tenant}"
        
        # Try to get token from cache first
        with self._cache_lock:
            cached_data = self._token_cache.get(cache_key)
            if cached_data:
                return cached_data['token']
        
        # If not in cache or expired, generate a new token
        print(f"Generating new token for tenant: {tenant}")
        
        payload = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "appToAccess": "llm-api",
        }
        headers = {
            'FlowTenant': tenant,
            'FlowAgent': self.flow_agent,
        }

        response = requests.post(token_url, json=payload, headers=headers)
        response_data = response.json()

        if 'access_token' not in response_data:
            raise ValueError("Failed to obtain access token", response_data)

        token = response_data['access_token']
        expires_in = response_data['expires_in']
        
        # Store the new token in cache with TTL
        with self._cache_lock:
            self._token_cache[cache_key] = {
                'token': token,
                'expires_at': time.time() + expires_in
            }
        
        return token

proxy_handler_instance = MyCustomHandler()
