from enum import Enum


class UserRole(str, Enum):
    user = "user"
    moderator = "moderator"
    admin = "admin"
    super_admin = "super_admin"
