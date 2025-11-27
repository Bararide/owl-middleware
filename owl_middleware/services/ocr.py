import io
import re
from typing import List, Tuple
from openai import OpenAI
import base64
import os
from PIL import Image, ImageDraw
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

    def parse_bounding_boxes(self, ocr_output: str) -> List[Tuple[str, List[int]]]:
        boxes = []

        pattern = r"([^[]+)\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]"

        matches = re.findall(pattern, ocr_output)
        for match in matches:
            text = match[0].strip()
            if text:
                coords = [int(match[1]), int(match[2]), int(match[3]), int(match[4])]
                boxes.append((text, coords))
                Logger.info(f"Found box: '{text[:50]}...' at {coords}")

        Logger.info(f"Parsed {len(boxes)} bounding boxes")
        return boxes

    def draw_bounding_boxes(self, image_data: bytes, ocr_output: str) -> bytes:
        try:
            boxes = self.parse_bounding_boxes(ocr_output)
            if not boxes:
                Logger.warning("No bounding boxes found to draw")
                return image_data

            image = Image.open(io.BytesIO(image_data)).convert("RGBA")

            overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)

            draw = ImageDraw.Draw(image)

            width, height = image.width, image.height
            Logger.info(f"Original image size: {width}, {height}")

            colors = [
                (255, 0, 0),  # red
                (0, 0, 255),  # blue
                (0, 128, 0),  # green
                (255, 165, 0),  # orange
                (128, 0, 128),  # purple
                (0, 255, 255),  # cyan
                (255, 0, 255),  # magenta
            ]

            transparent_colors = [
                (255, 0, 0, 80),  # red
                (0, 0, 255, 80),  # blue
                (0, 128, 0, 80),  # green
                (255, 165, 0, 80),  # orange
                (128, 0, 128, 80),  # purple
                (0, 255, 255, 80),  # cyan
                (255, 0, 255, 80),  # magenta
            ]

            max_y = max([bbox[3] for _, bbox in boxes])
            Logger.info(f"Max Y coordinate: {max_y}")

            for i, (_, bbox) in enumerate(boxes):
                color = colors[i % len(colors)]
                transparent_color = transparent_colors[i % len(transparent_colors)]

                x1, y1, x2, y2 = map(int, bbox)

                original_height = y2 - y1
                Logger.info(f"Box {i+1}: original height = {original_height}px")

                position_factor = y1 / max_y
                shift_amount = int(275 * position_factor)

                if original_height < 50:
                    height_multiplier = 1.6
                else:
                    height_multiplier = 1.3

                new_height = int(original_height * height_multiplier)

                y1_shifted = y1 + shift_amount
                y2_shifted = y1_shifted + new_height

                Logger.info(
                    f"Box {i+1}: original height={original_height}px, new height={new_height}px, shift={shift_amount}px"
                )

                draw_overlay.rectangle(
                    [x1, y1_shifted, x2, y2_shifted], fill=transparent_color
                )

                draw.rectangle([x1, y1_shifted, x2, y2_shifted], outline=color, width=3)

                text = str(i + 1)
                text_bbox = draw.textbbox((x1, y1_shifted - 15), text)
                draw.rectangle(text_bbox, fill=color)
                draw.text((x1, y1_shifted - 15), text, fill="white")

            image = Image.alpha_composite(image, overlay)

            image = image.convert("RGB")

            output_buffer = io.BytesIO()
            image.save(output_buffer, format="JPEG", quality=85)
            output_buffer.seek(0)

            Logger.info(f"Drew {len(boxes)} bounding boxes with transparent fill")
            return output_buffer.getvalue()

        except Exception as e:
            Logger.error(f"Error drawing bounding boxes: {e}")
            return image_data

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
