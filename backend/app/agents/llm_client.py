import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


class LLMUnavailableError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str = "mock"
    model_name: str = "rule-fallback"
    temperature: float = 0.3
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class LLMClient:
    """Small provider wrapper with graceful fallback behavior.

    Supported providers:
    - mock: always unavailable, so caller uses rule fallback.
    - openai: requires OPENAI_API_KEY and openai package.
    - gemini: requires GOOGLE_API_KEY and google-generativeai package.
    - minimax: OpenAI-compatible endpoint with MINIMAX_API_KEY.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()

    def generate_action_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        provider = self.config.provider.lower()
        if provider == "mock":
            raise LLMUnavailableError("mock provider does not generate model output")
        if provider == "openai":
            return self._generate_openai(system_prompt, user_prompt)
        if provider == "gemini":
            return self._generate_gemini(system_prompt, user_prompt)
        if provider == "minimax":
            return self._generate_minimax(system_prompt, user_prompt)
        raise LLMUnavailableError(f"unsupported provider: {self.config.provider}")

    @staticmethod
    def _extract_json_payload(text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise LLMUnavailableError("model returned empty content")

        # Handle markdown fenced code output.
        if "```" in text:
            parts = text.split("```")
            for block in parts:
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                if block.startswith("{") and block.endswith("}"):
                    try:
                        return json.loads(block)
                    except json.JSONDecodeError:
                        continue

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise LLMUnavailableError("model response is not valid JSON") from exc
            raise LLMUnavailableError("model response is not valid JSON")

    def _openai_compatible_generate(
        self,
        *,
        provider_name: str,
        api_key: Optional[str],
        system_prompt: str,
        user_prompt: str,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not api_key:
            raise LLMUnavailableError(f"{provider_name} api key is not set")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMUnavailableError("openai package is not installed") from exc

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=self.config.model_name,
            temperature=self.config.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Return strict JSON only with keys action_type and data.\n"
                        f"{user_prompt}"
                    ),
                },
            ],
        )
        try:
            text = response.choices[0].message.content or ""
        except (AttributeError, IndexError) as exc:
            raise LLMUnavailableError(f"{provider_name} returned no choices") from exc

        return self._extract_json_payload(text)

    def _generate_openai(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        return self._openai_compatible_generate(
            provider_name="openai",
            api_key=api_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            base_url=self.config.base_url,
        )

    def _generate_minimax(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        api_key = self.config.api_key or os.getenv("MINIMAX_API_KEY")
        base_url = self.config.base_url or os.getenv("MINIMAX_BASE_URL")
        return self._openai_compatible_generate(
            provider_name="minimax",
            api_key=api_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            base_url=base_url,
        )

    def _generate_gemini(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise LLMUnavailableError("GOOGLE_API_KEY is not set")

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise LLMUnavailableError("google-generativeai package is not installed") from exc

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.config.model_name)
        prompt = (
            f"{system_prompt}\n\n"
            "Return strict JSON only with keys action_type and data.\n"
            f"{user_prompt}"
        )
        response = model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        return self._extract_json_payload(text)
