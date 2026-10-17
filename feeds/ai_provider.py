import os
import re
import time
import json
import requests
from typing import Dict, Any, Optional

class AIProviderClient:
    """
    Unified AI Provider Client supporting Local Ollama and OpenAI-Compatible External Providers
    (OpenRouter, DeepSeek Cloud, OpenAI, Groq, custom proxy).
    Includes automatic failover to local Ollama.
    """
    def __init__(
        self,
        provider: str = "ollama",
        ollama_host: Optional[str] = None,
        ollama_model: Optional[str] = None,
        external_base_url: Optional[str] = None,
        external_api_key: Optional[str] = None,
        external_model: Optional[str] = None,
        fallback_to_local: bool = True,
        timeout: int = 40,
    ):
        p_raw = (provider or "ollama").lower()
        if p_raw in ("grok", "xai"):
            self.provider = "external"
            self.external_base_url = (external_base_url or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")).rstrip("/")
            self.external_api_key = external_api_key or os.getenv("XAI_API_KEY", os.getenv("EXTERNAL_AI_API_KEY", ""))
            self.external_model = external_model or os.getenv("XAI_MODEL", "grok-2-latest")
        else:
            self.provider = p_raw
            self.external_base_url = (external_base_url or os.getenv("EXTERNAL_AI_BASE_URL", "https://openrouter.ai/api/v1")).rstrip("/")
            self.external_api_key = external_api_key or os.getenv("EXTERNAL_AI_API_KEY", "")
            self.external_model = external_model or os.getenv("EXTERNAL_AI_MODEL", "deepseek/deepseek-r1")

        self.ollama_host = (ollama_host or os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434")).rstrip("/")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
        self.fallback_to_local = fallback_to_local
        self.timeout = timeout


    def generate(self, prompt: str, system_prompt: Optional[str] = None, format_json: bool = False) -> Dict[str, Any]:
        """
        Generate a completion using either external AI provider or local Ollama.
        Returns a dict: {"text": str, "provider_used": str, "model": str, "latency_ms": float, "fallback": bool}
        """
        start_time = time.time()

        if self.provider == "external" and self.external_api_key:
            try:
                res = self._call_external(prompt, system_prompt, format_json)
                latency = round((time.time() - start_time) * 1000, 1)
                return {
                    "text": res,
                    "provider_used": "external",
                    "model": self.external_model,
                    "latency_ms": latency,
                    "fallback": False
                }
            except Exception as e:
                if not self.fallback_to_local:
                    return {
                        "text": f"[AI-ERROR] External provider failed: {e}",
                        "provider_used": "external",
                        "model": self.external_model,
                        "latency_ms": round((time.time() - start_time) * 1000, 1),
                        "fallback": False,
                        "error": str(e)
                    }
                # Log fallback
                # Fall through to local Ollama

        # Local Ollama execution
        try:
            res = self._call_ollama(prompt, system_prompt, format_json)
            latency = round((time.time() - start_time) * 1000, 1)
            return {
                "text": res,
                "provider_used": "ollama",
                "model": self.ollama_model,
                "latency_ms": latency,
                "fallback": self.provider == "external"
            }
        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 1)
            return {
                "text": f"[AI-ERROR] Local Ollama failed: {e}",
                "provider_used": "ollama",
                "model": self.ollama_model,
                "latency_ms": latency,
                "fallback": False,
                "error": str(e)
            }

    def _call_ollama(self, prompt: str, system_prompt: Optional[str] = None, format_json: bool = False) -> str:
        url = f"{self.ollama_host}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        raw_text = resp.json().get("response", "")
        # Clean <think>...</think> tags if emitted by DeepSeek-R1
        clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        return clean_text

    def _call_external(self, prompt: str, system_prompt: Optional[str] = None, format_json: bool = False) -> str:
        url = f"{self.external_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.external_api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.external_model,
            "messages": messages,
            "temperature": 0.2
        }
        if format_json:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from external AI provider")
        raw_text = choices[0].get("message", {}).get("content", "")
        clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        return clean_text

    @staticmethod
    def test_connection(
        provider: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify connection and measure latency without impacting current active config.
        """
        start = time.time()
        provider = provider.lower()
        if provider == "ollama":
            host = (base_url or os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434")).rstrip("/")
            url = f"{host}/api/tags"
            try:
                resp = requests.get(url, timeout=5)
                resp.raise_for_status()
                models = [m.get("name") for m in resp.json().get("models", [])]
                latency = round((time.time() - start) * 1000, 1)
                return {"status": "online", "latency_ms": latency, "detail": f"Connected ({len(models)} models available)", "models": models}
            except Exception as e:
                return {"status": "offline", "latency_ms": 0, "detail": str(e)}
        else:
            base = (base_url or "https://openrouter.ai/api/v1").rstrip("/")
            if not api_key:
                return {"status": "unconfigured", "latency_ms": 0, "detail": "Missing API Key"}
            url = f"{base}/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            try:
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code in (200, 201):
                    latency = round((time.time() - start) * 1000, 1)
                    return {"status": "online", "latency_ms": latency, "detail": "Authenticated successfully"}
                else:
                    return {"status": "error", "latency_ms": 0, "detail": f"HTTP {resp.status_code}: {resp.text[:100]}"}
            except Exception as e:
                return {"status": "offline", "latency_ms": 0, "detail": str(e)}
