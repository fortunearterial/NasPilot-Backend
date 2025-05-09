from pydantic import BaseModel


class BaseSchema(BaseModel):
    id: str = None
