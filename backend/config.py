from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用配置
    APP_NAME: str = "MiniCodeAI"
    DEBUG: bool = True
    
    # 数据库配置 (MySQL)
    DATABASE_URL: str = "mysql+aiomysql://root:@localhost:3306/minicodeai"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Chroma向量库配置
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "documents"
    
    # DeepSeek API配置
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    # VLM模型配置
    QWEN_VL_API_KEY: Optional[str] = None
    QWEN_VL_BASE_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    
    # 网络搜索API
    TAVILY_API_KEY: Optional[str] = None
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 52428800  # 50MB
    
    # JWT配置
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

settings = Settings()