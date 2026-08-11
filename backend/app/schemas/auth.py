from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # A length floor is the only password rule here on purpose. Composition
    # rules ("one symbol, one digit") measurably push people toward shorter,
    # more predictable passwords, which is the opposite of the goal.
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str | None
    is_active: bool
