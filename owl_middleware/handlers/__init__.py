from .commnads import cmd_start, cmd_register
from .handlers import (
    handle_file_upload,
    handle_search,
    handle_read_file,
    handle_rebuild_index,
    handle_health_check,
    handle_list_files,
    handle_delete_file,
    handle_service_status,
    handle_create_container,
    handle_read_file_impl,
    handle_download_file,
    handle_select_container,
    handle_get_token,
)

from .http import http_router

__all__ = [
    "cmd_start",
    "cmd_register",
    "handle_file_upload",
    "handle_search",
    "handle_read_file",
    "handle_rebuild_index",
    "handle_health_check",
    "handle_list_files",
    "handle_delete_file",
    "handle_service_status",
    "handle_create_container",
    "handle_read_file_impl",
    "handle_download_file",
    "handle_select_container",
    "http_router",
    "handle_get_token",
]
