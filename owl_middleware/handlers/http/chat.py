from fastapi import APIRouter, HTTPException, Request
from fastbot.decorators import inject
from .dependencies import get_current_user_from_request
from services import ApiService, ContainerService, AuthService, AgentService
from models import User
from pampy import match, _
import logging

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("")
@inject("api_service")
@inject("container_service")
@inject("auth_service")
@inject("agent_service")
@inject("deepseek_agent_service")
async def chat_with_bot(
    request: dict,
    req: Request,
    api_service: ApiService,
    container_service: ContainerService,
    auth_service: AuthService,
    agent_service: AgentService,
    deepseek_agent_service: AgentService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    query = request.get("query", "").strip()
    container_id = request.get("container_id")
    conversation_history = request.get("conversation_history", [])
    model = request.get("model", 0)
    limit = request.get("limit", 5)

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    if not container_id:
        raise HTTPException(status_code=400, detail="Container ID is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err() or not container_result.unwrap():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    search_result = await api_service.containers.semantic_search(
        query, current_user, container, limit
    )
    if search_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Search error: {search_result.unwrap_err()}"
        )

    search_data = search_result.unwrap()

    context_parts = []
    used_files = []

    for file_info in reversed(search_data.get("results", [])):
        file_path = file_info.get("path", "")
        file_id = file_path.split("/")[-1] if "/" in file_path else file_path

        content_result = await api_service.files.get_file_content(file_id, container_id)
        content_snippet = ""
        if content_result.is_ok():
            content_data = content_result.unwrap()
            if isinstance(content_data, str):
                content_snippet = content_data
            elif isinstance(content_data, dict) and "content" in content_data:
                content_snippet = content_data["content"]

        file_name = file_path.split("/")[-1] if "/" in file_path else file_id
        context_parts.append(f"File: {file_name}")
        context_parts.append(f"Path: {file_path}")
        if content_snippet:
            context_parts.append(f"Content: {content_snippet}")
        else:
            context_parts.append("Content: [No content available]")
        context_parts.append("---")

        used_files.append(
            {
                "file_path": file_path,
                "file_name": file_name,
                "relevance_score": file_info.get("score", 0.0),
                "content_snippet": content_snippet if content_snippet else "",
            }
        )

    context = "\n".join(context_parts) if context_parts else "No relevant files found."

    system_prompt = f"""You are an AI assistant that helps users analyze their files.

Context from files:
{context}

User question: {query}

Analyze the file contents and provide a helpful response."""

    chat_result = match(
        model,
        0,
        await agent_service.chat(
            message=query,
            conversation_history=conversation_history,
            user=current_user,
            system_prompt=system_prompt,
        ),
        1,
        await deepseek_agent_service.chat(
            message=query,
            conversation_history=conversation_history,
            user=current_user,
            system_prompt=system_prompt,
        ),
    )

    if chat_result.is_err():
        error_msg = str(chat_result.unwrap_err())
        logger.error(f"Chat error: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Chat error: {error_msg}")

    chat_response = chat_result.unwrap()

    return {
        "data": {
            "answer": chat_response.get("content", ""),
            "used_files": used_files,
            "conversation_history": chat_response.get("conversation_history", []),
            "model": chat_response.get("model", ""),
            "metadata": chat_response.get("metadata", {}),
        }
    }
