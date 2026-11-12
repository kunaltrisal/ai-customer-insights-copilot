"""Thin wrapper around the Gemini API.

Every AI call in the app goes through this file, so there is one place
that handles the API key, retries and token counting.
"""
import json
import time

from pydantic import BaseModel


class LLMError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai  # imported here so tests can run without it

        self._genai = genai
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def _call(self, prompt: str, config) -> object:
        last_error = None
        for attempt in range(5):
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
                self.calls += 1
                usage = getattr(resp, "usage_metadata", None)
                if usage is not None:
                    self.input_tokens += usage.prompt_token_count or 0
                    self.output_tokens += usage.candidates_token_count or 0
                return resp
            except Exception as e:  # rate limits (429) and overloads (503) are worth retrying
                last_error = e
                msg = str(e)
                retryable = any(code in msg for code in ("429", "500", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"))
                if not retryable:
                    break
                time.sleep(min(60, 5 * 2**attempt))
        raise LLMError(f"Gemini call failed: {last_error}")

    def generate_json(self, prompt: str, schema: type[BaseModel], temperature: float = 0.0) -> BaseModel:
        """Ask for a reply that must match `schema` (structured output)."""
        types = self._genai.types
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )
        resp = self._call(prompt, config)
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        try:
            return schema.model_validate(json.loads(resp.text))
        except Exception as e:
            raise LLMError(f"Gemini returned JSON that did not match the expected shape: {e}")

    def generate_text(self, prompt: str, temperature: float = 0.3) -> str:
        types = self._genai.types
        resp = self._call(prompt, types.GenerateContentConfig(temperature=temperature))
        return (resp.text or "").strip()

    def usage(self) -> dict:
        return {"api_calls": self.calls, "input_tokens": self.input_tokens, "output_tokens": self.output_tokens}
