from typing import Optional
from models import User
from state import State


class StateService:
    def __init__(self):
        self.state = State()

    async def set_user_work_container(self, user: User, container_id: str) -> None:
        self.state.set_work_container(str(user.id), container_id)

    async def get_user_work_container(self, user: User) -> Optional[str]:
        return self.state.get_work_container(str(user.id))

    async def clear_user_work_container(self, user: User) -> None:
        self.state.clear_work_container(str(user.id))

    async def has_work_container(self, user: User) -> bool:
        return self.state.get_work_container(str(user.id)) is not None
