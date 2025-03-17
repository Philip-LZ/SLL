import os
import json
import threading
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path

import litellm

# 配置litellm缓存
litellm.drop_params = True
litellm.telemetry = False
from litellm.caching.caching import Cache

disk_cache_dir = os.path.join(Path.home(), ".storm_local_cache")
litellm.cache = Cache(disk_cache_dir=disk_cache_dir, type="disk")

class LitellmModel:
    """基础语言模型类，提供缓存和使用统计功能"""
    def __init__(
        self,
        model: str = "openai/gpt-4",
        api_key: Optional[str] = None,
        model_type: Literal["chat", "text"] = "chat",
        temperature: float = 0.0,
        max_tokens: int = 1000,
        cache: bool = True,
        **kwargs
    ):
        self.model = model
        self.model_type = model_type
        self.cache = cache
        self.kwargs = dict(temperature=temperature, max_tokens=max_tokens, **kwargs)
        self.history = []
        self._token_usage_lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def log_usage(self, response):
        """记录token使用情况"""
        usage_data = response.get("usage")
        if usage_data:
            with self._token_usage_lock:
                self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                self.completion_tokens += usage_data.get("completion_tokens", 0)

    def get_usage_and_reset(self):
        """获取并重置token使用统计"""
        usage = {
            self.model: {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
            }
        }
        self.prompt_tokens = 0
        self.completion_tokens = 0
        return usage

    def __call__(self, prompt=None, messages=None, **kwargs):
        cache = kwargs.pop("cache", self.cache)
        messages = messages or [{"role": "user", "content": prompt}]
        kwargs = {**self.kwargs, **kwargs}

        response = litellm.completion(
            model=self.model,
            messages=messages,
            cache={"no-cache": not cache, "no-store": not cache},
            **kwargs
        )

        response_dict = response.json()
        self.log_usage(response_dict)
        outputs = [
            c.message.content if hasattr(c, "message") else c["text"]
            for c in response["choices"]
        ]

        entry = dict(
            prompt=prompt,
            messages=messages,
            kwargs={k: v for k, v in kwargs.items() if not k.startswith("api_")},
            response=response_dict,
            outputs=outputs,
            usage=dict(response_dict["usage"]),
            cost=response.get("_hidden_params", {}).get("response_cost")
        )
        self.history.append(entry)

        return outputs