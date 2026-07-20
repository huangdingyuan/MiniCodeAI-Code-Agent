from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键id")
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="会话ID")
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="所属用户id")
    history: Mapped[str | None] = mapped_column(Text, default=None, comment="对话历史(JSON字符串)")
    create_time: Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), default=func.now(), comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), default=func.now(), onupdate=func.now(), comment="更新时间")
