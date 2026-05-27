from enum import Enum


class ContainerPermission(str, Enum):
    read_only = "read_only"
    read_write = "read_write"
    admin = "admin"
