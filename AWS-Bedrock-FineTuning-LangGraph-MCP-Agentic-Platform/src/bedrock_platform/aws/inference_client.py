import time

import boto3
from pydantic import BaseModel, ConfigDict


class InferenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class InferenceClient:
    def __init__(self, session: boto3.Session | None = None) -> None:
        self._session = session or boto3.Session()
        self._bedrock_runtime = self._session.client("bedrock-runtime")

    def _converse(
        self, model_id: str, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        start = time.perf_counter()
        response = self._bedrock_runtime.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": max_tokens},
        )
        latency_ms = (time.perf_counter() - start) * 1000

        output_message = response["output"]["message"]
        text = "".join(block.get("text", "") for block in output_message["content"])
        usage = response["usage"]

        return InferenceResult(
            text=text,
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
            latency_ms=round(latency_ms, 2),
        )

    def invoke_base_model(
        self, base_model_id: str, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        return self._converse(base_model_id, system_prompt, user_prompt, max_tokens)

    def invoke_tuned_model(
        self, deployment_arn: str, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        return self._converse(deployment_arn, system_prompt, user_prompt, max_tokens)
