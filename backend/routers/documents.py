from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import os
import uuid

from database import get_db
from models.document import Document
from models.user import User
from utils.auth import get_current_user
from config import settings
from services.document_parser import DocumentParser

router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传文档"""
    # 检查文件类型
    allowed_types = ["pdf", "png", "jpg", "jpeg", "md", "txt", "docx", "doc"]
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型，支持: {', '.join(allowed_types)}"
        )
    
    # 生成唯一文件名
    file_id = str(uuid.uuid4())
    filename = f"{file_id}.{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    
    # 保存文件
    content = await file.read()
    file_size = len(content)
    
    # 检查文件大小
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制 ({settings.MAX_FILE_SIZE / 1024 / 1024}MB)"
        )
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 创建文档记录
    new_document = Document(
        filename=file.filename,
        file_type=file_ext,
        file_size=file_size,
        status="parsing",
        user_id=current_user.id
    )
    
    db.add(new_document)
    await db.commit()
    await db.refresh(new_document)
    
    # 异步解析文档并添加到向量库
    try:
        from services.document_parser import DocumentParser
        from services.vector_store import vector_store

        parser = DocumentParser()

        # 解析文档内容
        text_content = parser.parse_file(file_path, file_ext)

        # 添加到向量库（使用全局单例，确保 BM25 索引共享）
        vector_store.add_document(
            doc_id=str(new_document.doc_id),
            text=text_content,
            metadata={"filename": file.filename, "file_type": file_ext}
        )
        
        # 更新状态为就绪
        new_document.status = "ready"
        await db.commit()
        
    except Exception as e:
        # 解析失败，更新状态为失败
        new_document.status = "failed"
        await db.commit()
        print(f"文档解析失败: {e}")
    
    return {
        "task_id": file_id,
        "doc_id": new_document.doc_id,
        "filename": file.filename,
        "status": new_document.status
    }


@router.get("", response_model=List[dict])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文档列表"""
    query = select(Document).where(Document.user_id == current_user.id).order_by(Document.upload_time.desc())
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return [
        {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "upload_time": doc.upload_time.isoformat(),
            "status": doc.status
        }
        for doc in documents
    ]


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除文档"""
    query = select(Document).where(Document.doc_id == doc_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 验证文档所有权
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此文档"
        )

    # 删除文件
    file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.{document.file_type}")
    if os.path.exists(file_path):
        os.remove(file_path)

    # 从向量库中删除相关数据
    try:
        from services.vector_store import vector_store
        vector_store.delete_document(str(doc_id))
    except Exception as e:
        print(f"从向量库删除文档失败: {e}")

    # 删除数据库记录
    await db.delete(document)
    await db.commit()

    return {"message": "文档已删除"}


@router.get("/{doc_id}/preview")
async def preview_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """FR-5 文档预览：返回文档解析后的纯文本内容（仅文本预览）"""
    query = select(Document).where(Document.doc_id == doc_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 验证文档所有权
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此文档"
        )

    # 优先从向量库读取已切分的文本块（避免重复解析）
    try:
        from services.vector_store import vector_store
        chunks = vector_store.get_document_chunks(str(doc_id))
        if chunks:
            # 按 chunk_index 排序拼接
            chunks_sorted = sorted(
                chunks,
                key=lambda c: c.get("metadata", {}).get("chunk_index", 0)
            )
            full_text = "\n\n".join([c["content"] for c in chunks_sorted])
            return {
                "doc_id": doc_id,
                "filename": document.filename,
                "file_type": document.file_type,
                "preview": full_text,
                "chunk_count": len(chunks),
                "source": "vector_store",
            }
    except Exception as e:
        print(f"从向量库读取预览失败: {e}")

    # 回退：重新解析文件
    file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.{document.file_type}")
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始文件不存在，可能已被删除"
        )

    try:
        text_content = DocumentParser.parse_file(file_path, document.file_type)
        return {
            "doc_id": doc_id,
            "filename": document.filename,
            "file_type": document.file_type,
            "preview": text_content,
            "chunk_count": 0,
            "source": "file_reparsed",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档解析失败: {str(e)}"
        )
