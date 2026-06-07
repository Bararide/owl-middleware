from enum import Enum


class GroupRole(str, Enum):
    admin = "admin"
    member = "member"
    moderator = "moderator"
