from openai import OpenAI
import base64
import os
from fastbot.core import Ok, Err, Result
from fastbot.logger.logger import Logger


class Ocr:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("NOVITA_API_KEY")
        self.base_url = base_url or "https://api.novita.ai/openai"

        Logger.info(f"Initializing OCR with correct Novita API")
        Logger.info(f"Base URL: {self.base_url}")

        try:
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            Logger.info("OpenAI client initialized with correct Novita endpoint")
        except Exception as e:
            Logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    def clean_html_tags(self, text: str) -> str:
        import re

        text = re.sub(r"<[^>]+>", "", text)

        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)
        text = text.strip()

        return text

    async def extract_from_bytes(
        self, file_data: bytes, filename: str = "document"
    ) -> Result[str, Exception]:
        try:
            Logger.info(f"Starting OCR for: {filename}, size: {len(file_data)} bytes")

            base64_image = base64.b64encode(file_data).decode("utf-8")

            import asyncio

            result = await asyncio.get_event_loop().run_in_executor(
                None, self._make_correct_ocr_request, base64_image
            )

            return result

        except Exception as e:
            Logger.error(f"Error in extract_from_bytes: {e}")
            return Err(e)

    def _make_correct_ocr_request(self, base64_image: str) -> Result[str, Exception]:
        try:
            response = self.client.chat.completions.create(
                model="deepseek/deepseek-ocr",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                            {
                                "type": "text",
                                "text": "<|grounding|>OCR this image and return only the text content without any coordinates or bounding boxes.",
                            },
                        ],
                    }
                ],
                stream=False,
                max_tokens=4096,
            )

            content = response.choices[0].message.content
            return Ok(content.strip())

        except Exception as e:
            Logger.error(f"OCR API call failed: {e}")
        return Err(e)

    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
