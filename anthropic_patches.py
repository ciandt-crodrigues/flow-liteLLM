import json
import traceback
from fastapi import HTTPException
from litellm.proxy.proxy_server import UserAPIKeyAuth, ProxyException
from litellm.llms.anthropic.experimental_pass_through.messages.transformation import (
    AnthropicMessagesConfig,
)
from litellm.proxy.anthropic_endpoints import endpoints

# Store the original functions
previous_transform = AnthropicMessagesConfig.transform_anthropic_messages_request
original_async_data_generator = endpoints.async_data_generator_anthropic

def custom_transform_anthropic_messages_request(*args, **kwargs):
    # You can add custom logic here before or after calling the original function
    base_request = previous_transform(*args, **kwargs)

    if "model" in kwargs and kwargs["model"] and "allowedModels" not in base_request:
        base_request["allowedModels"] = [kwargs["model"]]
    if "anthropic_version" not in base_request:
        base_request["anthropic_version"] = "bedrock-2023-05-31"
    if "metadata" in base_request:
        del base_request["metadata"]
    return base_request

async def patched_async_data_generator_anthropic(
    response,
    user_api_key_dict,
    request_data,
    proxy_logging_obj,
):
    try:
        async for chunk in response:
            endpoints.verbose_proxy_logger.debug(
                "async_data_generator: received streaming chunk - {}".format(chunk)
            )
            ### CALL HOOKS ### - modify outgoing data
            chunk = await proxy_logging_obj.async_post_call_streaming_hook(
                user_api_key_dict=user_api_key_dict, response=chunk
            )

            # Fix: Convert dictionary to JSON string if needed
            if isinstance(chunk, dict):
                chunk = f"data: {json.dumps(chunk)}\n\n"
                
            yield chunk
    except Exception as e:
        endpoints.verbose_proxy_logger.exception(
            "litellm.proxy.proxy_server.async_data_generator(): Exception occured - {}".format(
                str(e)
            )
        )
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict,
            original_exception=e,
            request_data=request_data,
        )
        endpoints.verbose_proxy_logger.debug(
            f"\033[1;31mAn error occurred: {e}\n\n Debug this by setting `--debug`, e.g. `litellm --model gpt-3.5-turbo --debug`"
        )

        if isinstance(e, HTTPException):
            raise e
        else:
            error_traceback = traceback.format_exc()
            error_msg = f"{str(e)}\n\n{error_traceback}"

        proxy_exception = ProxyException(
            message=getattr(e, "message", error_msg),
            type=getattr(e, "type", "None"),
            param=getattr(e, "param", "None"),
            code=getattr(e, "status_code", 500),
        )
        error_returned = json.dumps({"error": proxy_exception.to_dict()})
        yield f"data: {error_returned}\n\n"

# Function to apply the patches
def apply_anthropic_patches():
    # Apply the monkey patches
    AnthropicMessagesConfig.transform_anthropic_messages_request = custom_transform_anthropic_messages_request
    endpoints.async_data_generator_anthropic = patched_async_data_generator_anthropic