from pydantic import BaseModel, EmailStr
from typing import Optional


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    email: str
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """消息响应"""
    message: str
    success: bool = True


class AvatarResponse(BaseModel):
    """头像上传响应"""
    avatar: str
    message: str = "头像更新成功"