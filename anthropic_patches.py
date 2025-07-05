from typing import Dict, List, cast
from litellm import Deployment, GenericLiteLLMParams, LiteLLM_Params
from litellm.router import Router
from litellm.router_utils.clientside_credential_handler import (
    get_dynamic_litellm_params
)
from litellm.llms.bedrock.messages.invoke_transformations.anthropic_claude3_transformation import AmazonAnthropicClaude3MessagesConfig


original_transform_anthropic_messages_request = AmazonAnthropicClaude3MessagesConfig.transform_anthropic_messages_request

def transform_anthropic_messages_request(
        self,
        model: str,
        messages: List[Dict],
        anthropic_messages_optional_request_params: Dict,
        litellm_params: GenericLiteLLMParams,
        headers: dict,
    ) -> Dict:
    original_transform = original_transform_anthropic_messages_request(
        self=self,
        model=model,
        messages=messages,
        anthropic_messages_optional_request_params=anthropic_messages_optional_request_params,
        litellm_params=litellm_params,
        headers=headers,
    )
    if "metadata" in original_transform:
        del original_transform["metadata"]
    return original_transform
    
def custom_handle_clientside_credential(
    self: Router, deployment: dict, kwargs: dict
) -> Deployment:
    """
    Handle clientside credential
    """
    model_info = deployment.get("model_info", {}).copy()
    litellm_params = deployment["litellm_params"].copy()
    dynamic_litellm_params = get_dynamic_litellm_params(
        litellm_params=litellm_params, request_kwargs=kwargs
    )
    metadata = kwargs.get("metadata", {})
    model_group = cast(str, metadata.get("model_group"))
    _model_id = self._generate_model_id(
        model_group=model_group, litellm_params=dynamic_litellm_params
    )
    original_model_id = model_info.get("id")
    model_info["id"] = _model_id
    model_info["original_model_id"] = original_model_id
    deployment_pydantic_obj = Deployment(
        model_name=model_group,
        litellm_params=LiteLLM_Params(**dynamic_litellm_params),
        model_info=model_info,
    )
    self.upsert_deployment(
        deployment=deployment_pydantic_obj
    )  # add new deployment to router
    return deployment_pydantic_obj

# Function to apply the patches
def apply_anthropic_patches():
    # Apply the monkey patches
    Router._handle_clientside_credential = custom_handle_clientside_credential
    AmazonAnthropicClaude3MessagesConfig.transform_anthropic_messages_request = transform_anthropic_messages_request
