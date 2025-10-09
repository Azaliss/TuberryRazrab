from pydantic import BaseModel
from pydantic import ConfigDict


class ProjectSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    master_bot_token: str | None = None
    master_bot_name: str | None = None


class ProjectSettingsUpdateRequest(BaseModel):
    master_bot_token: str | None = None
    master_bot_name: str | None = None


class TelegramConfigResponse(BaseModel):
    bot_username: str | None = None
