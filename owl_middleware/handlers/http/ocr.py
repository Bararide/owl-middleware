from fastapi import APIRouter, HTTPException, Request
from fastbot.decorators import inject
from services import ApiService, ContainerService, AuthService, Ocr
from models import User
from datetime import datetime
import base64
import logging

router = APIRouter(prefix="/ocr", tags=["ocr"])
logger = logging.getLogger(__name__)


@router.post("/process")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
@inject("ocr_service")
async def process_ocr(
    request: dict,
    req: Request,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
    ocr_service: Ocr,
):
    token = None
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = req.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user = user_result.unwrap()

    container_id = request.get("container_id")
    file_data_base64 = request.get("file_data")
    file_name = request.get("file_name")
    mime_type = request.get("mime_type", "image/jpeg")

    if not container_id:
        raise HTTPException(status_code=400, detail="Container ID is required")
    if not file_data_base64:
        raise HTTPException(status_code=400, detail="File data is required")
    if not file_name:
        raise HTTPException(status_code=400, detail="File name is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        file_data = base64.b64decode(file_data_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file data encoding")

    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    supported_formats = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".pdf"]
    if not any(file_name.lower().endswith(ext) for ext in supported_formats):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    ocr_result = await ocr_service.extract_from_bytes(file_data, file_name)
    if ocr_result.is_err():
        logger.error(f"OCR processing failed: {ocr_result.unwrap_err()}")
        raise HTTPException(
            status_code=500, detail=f"OCR processing failed: {ocr_result.unwrap_err()}"
        )

    extracted_text = ocr_result.unwrap()
    cleaned_text = ocr_service.clean_html_tags(extracted_text)

    visualized_data = None
    boxes_count = 0
    if file_name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff")):
        try:
            visualized_data = ocr_service.draw_bounding_boxes(file_data, extracted_text)
            boxes = ocr_service.parse_bounding_boxes(extracted_text)
            boxes_count = len(boxes)
        except Exception:
            visualized_data = None

    result_file_name = f"ocr_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_name.split('.')[0]}.txt"

    api_result = await api_service.files.create_file(
        path=result_file_name,
        content=cleaned_text,
        user_id=str(current_user.id),
        container_id=container_id,
    )
    if api_result.is_err():
        logger.error(
            f"Failed to save OCR result to container: {api_result.unwrap_err()}"
        )

    response_data = {
        "text": cleaned_text,
        "confidence": 0.95,
        "processing_time": 0,
        "file_name": file_name,
        "extracted_text_length": len(cleaned_text),
        "boxes_count": boxes_count,
        "has_visualization": visualized_data is not None,
    }

    if visualized_data:
        response_data["visualization"] = base64.b64encode(visualized_data).decode(
            "utf-8"
        )
        response_data["visualization_format"] = "image/jpeg"

    return {"data": response_data}
