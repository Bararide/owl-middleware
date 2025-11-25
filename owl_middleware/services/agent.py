import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

from models import User
from fastbot.core import Result, result_try, Err, Ok

from agentics import PromptEngine, MistralModel, PromptFactory, BasePrompt


class AgentService:
    def __init__(
        self,
        api_key: str,
        prompts_dir: str = "prompts",
        default_model: str = "mistral-large-latest",
        default_temperature: float = 0.7,
    ):
        self._api_key = api_key
        self._model_name = default_model
        self._temperature = default_temperature
        self._prompts_dir = prompts_dir

        self._prompt_engine: Optional[PromptEngine] = None
        self._llm_model: Optional[MistralModel] = None
        self._initialized = False

        self._prompt_cache: Dict[str, BasePrompt] = {}

    @property
    def api_key(self) -> str:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value
        self._initialized = False

    @property
    def model(self) -> str:
        return self._model_name

    @model.setter
    def model(self, value: str):
        self._model_name = value
        self._initialized = False

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float):
        self._temperature = max(0.0, min(2.0, value))
        if self._llm_model:
            self._llm_model.config.temperature = self._temperature

    async def initialize(self) -> Result[bool, str]:
        try:
            if not self._api_key:
                return Err("API ключ не установлен")

            Path(self._prompts_dir).mkdir(exist_ok=True)

            self._prompt_engine = PromptEngine(self._prompts_dir)

            model_config = {
                "model_name": self._model_name,
                "api_key": self._api_key,
                "temperature": self._temperature,
            }
            self._llm_model = MistralModel(model_config)

            self._initialized = True
            return Ok(True)

        except Exception as e:
            return Err(f"Ошибка инициализации: {str(e)}")

    async def _ensure_initialized(self) -> Result[bool, str]:
        if not self._initialized or not self._llm_model:
            return await self.initialize()
        return Ok(True)

    @result_try
    async def generate_response(
        self,
        prompt_type: str,
        context: Dict[str, Any],
        user: Optional[User] = None,
        **kwargs,
    ) -> Result[Dict[str, Any], str]:
        init_result = await self._ensure_initialized()
        if init_result.is_err:
            return Err(init_result.err_value)

        try:
            if prompt_type.endswith(".jinja2"):
                rendered = await self._prompt_engine.render(prompt_type, **context)
                prompt_text = rendered["text"]
            else:
                prompt = self._get_cached_prompt(prompt_type, **kwargs)
                prompt_text = prompt.format(**context)

            response = await self._llm_model.generate(prompt_text)

            return Ok(
                {
                    "content": response.content,
                    "model": response.model_name,
                    "prompt_type": prompt_type,
                    "finish_reason": response.finish_reason,
                    "user_id": user.id if user else None,
                    "metadata": {
                        "temperature": self._temperature,
                        "tokens_used": getattr(response, "usage", {}).get(
                            "total_tokens", 0
                        ),
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                }
            )

        except Exception as e:
            return Err(f"Ошибка генерации ответа: {str(e)}")

    def _get_cached_prompt(self, prompt_type: str, **kwargs) -> BasePrompt:
        cache_key = f"{prompt_type}_{str(kwargs)}"

        if cache_key not in self._prompt_cache:
            self._prompt_cache[cache_key] = PromptFactory.create_prompt(
                prompt_type, **kwargs
            )

        return self._prompt_cache[cache_key]

    def _build_user_context(self, user: User) -> Dict[str, Any]:
        return {
            "user_name": user.last_name,
            "user_id": user.id,
            "user_language": getattr(user, "language", "ru"),
        }

    @result_try
    async def chat(
        self,
        message: str,
        conversation_history: List[Dict[str, str]] = None,
        user: Optional[User] = None,
        system_prompt: str = None,
    ) -> Result[Dict[str, Any], str]:
        conversation_history = conversation_history or []

        context = {
            "history": conversation_history,
            "message": message,
            "system_prompt": system_prompt or "Ты полезный AI ассистент.",
        }

        if user:
            context.update(self._build_user_context(user))

        result = await self.generate_response("chat", context, user)

        if result.is_ok:
            response_data = result.ok_value
            new_history = conversation_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response_data["content"]},
            ]
            response_data["conversation_history"] = new_history[-10:]

        return result

    @result_try
    async def rag_query(
        self, question: str, context: str, user: Optional[User] = None
    ) -> Result[Dict[str, Any], str]:
        rag_context = {"question": question, "context": context}

        return await self.generate_response("rag", rag_context, user)

    @result_try
    async def summarize_text(
        self, text: str, user: Optional[User] = None, max_length: int = 500
    ) -> Result[Dict[str, Any], str]:
        summary_context = {"text": text, "max_length": max_length}

        return await self.generate_response("summary", summary_context, user)

    @result_try
    async def batch_process(
        self, requests: List[Dict[str, Any]]
    ) -> Result[List[Dict[str, Any]], str]:
        init_result = await self._ensure_initialized()
        if init_result.is_err:
            return Err(init_result.err_value)

        try:
            tasks = []
            for req in requests:
                prompt_type = req.get("prompt_type", "rag")
                context = req.get("context", {})
                user = req.get("user")

                task = self.generate_response(prompt_type, context, user)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append(
                        {"error": str(result), "success": False, "index": i}
                    )
                elif hasattr(result, "is_ok"):
                    if result.is_ok:
                        processed_results.append(
                            {**result.ok_value, "success": True, "index": i}
                        )
                    else:
                        processed_results.append(
                            {"error": result.err_value, "success": False, "index": i}
                        )

            return Ok(processed_results)

        except Exception as e:
            return Err(f"Ошибка пакетной обработки: {str(e)}")

    @result_try
    async def get_available_prompts(self) -> Result[List[str], str]:
        init_result = await self._ensure_initialized()
        if init_result.is_err:
            return Err(init_result.err_value)

        try:
            factory_prompts = PromptFactory.get_available_prompts()

            file_templates = self._prompt_engine.list_templates()

            all_prompts = factory_prompts + file_templates
            return Ok(all_prompts)

        except Exception as e:
            return Err(f"Ошибка получения списка промптов: {str(e)}")

    async def health_check(self) -> Dict[str, Any]:
        try:
            init_result = await self._ensure_initialized()

            if init_result.is_err:
                return {
                    "status": "unhealthy",
                    "error": init_result.err_value,
                    "initialized": False,
                }

            test_result = await self.generate_response(
                "summary", {"text": "Тестовый текст для проверки здоровья сервиса."}
            )

            return {
                "status": "healthy" if test_result.is_ok else "degraded",
                "initialized": self._initialized,
                "model": self._model_name,
                "prompts_available": (
                    len((await self.get_available_prompts()).ok_value)
                    if test_result.is_ok
                    else 0
                ),
                "test_successful": test_result.is_ok,
                "error": test_result.err_value if test_result.is_err else None,
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "initialized": False}

    async def cleanup(self):
        """Очистка ресурсов."""
        self._prompt_cache.clear()
        self._initialized = False
        self._prompt_engine = None
        self._llm_model = None
