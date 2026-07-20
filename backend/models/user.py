from datetime import datetime
from sqlalchemy import Integer, String, DateTime, func, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键id")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True, comment="邮箱")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, comment="加密密码")
    # 使用 LONGTEXT 避免大图 Base64 被截断（Text 仅 64KB，LONGTEXT 最大 4GB）
    avatar: Mapped[str] = mapped_column(LONGTEXT, nullable=True, comment="头像URL或Base64数据")
    create_time: Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), default=func.now(), comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), default=func.now(), onupdate=func.now(), comment="更新时间")
