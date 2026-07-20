from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键id")
    filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="文件名")
    file_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="文件类型")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, comment="文件大小(字节)")
    upload_time: Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), default=func.now(), comment="上传时间")
    status: Mapped[str] = mapped_column(String(20), default="parsing", comment="状态: parsing/ready/error")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="所属用户id")

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键id")
    doc_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.doc_id"), nullable=False, comment="所属文档id")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="文本内容")
    chunk_metadata: Mapped[str | None] = mapped_column("metadata", Text, default=None, comment="元数据(JSON字符串)")

    document: Mapped["Document"] = relationship(back_populates="chunks")
