"""
图片识别路由
提供图片上传和识别功能
"""
import os
import shutil
import tempfile
from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import JSONResponse

from services.document_parser import DocumentParser
from utils.auth import get_current_user

router = APIRouter(tags=["图片识别"])


@router.post("/recognize")
async def recognize_image(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """
    识别图片内容
    支持使用 VLM（通义千问）或 OCR 识别图片中的文字和内容
    
    Args:
        file: 图片文件（png, jpg, jpeg, gif, bmp, webp）
        
    Returns:
        识别结果，包含图片描述和提取的文字
    """
    file_ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
    
    if file_ext not in ["png", "jpg", "jpeg", "gif", "bmp", "webp"]:
        return JSONResponse(
            status_code=400,
            content={"error": "不支持的图片格式"}
        )
    
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=f".{file_ext}",
            dir=tempfile.gettempdir()
        ) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
        
        try:
            result = DocumentParser.parse_file(temp_path, file_ext)
            
            return JSONResponse(content={
                "success": True,
                "content": result,
                "filename": file.filename,
                "file_type": file_ext
            })
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"图片识别失败: {str(e)}"}
        )
