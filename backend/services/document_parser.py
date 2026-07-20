"""
文档解析服务
支持 PDF、TXT、MD、DOCX、PNG、JPG、JPEG 等格式的文档解析和文本提取
"""
import os
import logging
import base64
from typing import List, Dict, Any
from pathlib import Path

from pypdf import PdfReader
from docx import Document as DocxDocument
import markdown
from PIL import Image

logger = logging.getLogger(__name__)

# 尝试导入 EasyOCR
try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False
    easyocr = None

# 全局 EasyOCR 阅读器（懒加载）
_ocr_reader = None


def _get_ocr_reader():
    """获取 EasyOCR 阅读器（懒加载）"""
    global _ocr_reader
    if _ocr_reader is None:
        if not _EASYOCR_AVAILABLE:
            raise ImportError("EasyOCR 未安装，无法使用本地 OCR")
        logger.info("正在初始化 EasyOCR 模型（首次加载可能需要一些时间）...")
        _ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
    return _ocr_reader


class DocumentParser:
    """文档解析器"""

    @staticmethod
    def parse_file(file_path: str, file_type: str) -> str:
        """
        解析文件并提取文本内容
        
        Args:
            file_path: 文件路径
            file_type: 文件类型（pdf, txt, md, docx）
            
        Returns:
            提取的文本内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在：{file_path}")

        file_type = file_type.lower()
        
        if file_type == 'pdf':
            return DocumentParser._parse_pdf(file_path)
        elif file_type == 'txt':
            return DocumentParser._parse_txt(file_path)
        elif file_type == 'md':
            return DocumentParser._parse_md(file_path)
        elif file_type == 'docx':
            return DocumentParser._parse_docx(file_path)
        elif file_type == 'doc':
            return DocumentParser._parse_doc(file_path)
        elif file_type in ['png', 'jpg', 'jpeg', 'bmp', 'gif']:
            return DocumentParser._parse_image(file_path)
        else:
            raise ValueError(f"不支持的文件类型：{file_type}")

    @staticmethod
    def _parse_pdf(file_path: str) -> str:
        """FR-2 解析 PDF 文件（增强版）：提取文本、表格，并标注页码
        使用 [[PAGE:N]] 标记每个 chunk 所属的页码，便于精确引用
        """
        try:
            reader = PdfReader(file_path)
            text_parts = []

            for page_num, page in enumerate(reader.pages, 1):
                # FR-2 提取页面文本
                page_text = page.extract_text() or ""

                # FR-2 提取表格（尝试使用 pdfplumber 获取更精确的表格）
                table_text = DocumentParser._extract_pdf_tables(file_path, page_num)
                if table_text:
                    page_text = page_text + "\n\n[表格内容]\n" + table_text

                if page_text.strip():
                    # FR-11 使用 [[PAGE:N]] 标记页码（vector_store 会解析并清理）
                    text_parts.append(f"[[PAGE:{page_num}]]\n{page_text}")

            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF 解析失败：{e}")
            raise

    @staticmethod
    def _extract_pdf_tables(file_path: str, page_num: int) -> str:
        """FR-2 提取 PDF 指定页的表格内容（使用 pdfplumber）"""
        try:
            import pdfplumber
            tables_text = []
            with pdfplumber.open(file_path) as pdf:
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    tables = page.extract_tables()
                    for t_idx, table in enumerate(tables, 1):
                        if not table:
                            continue
                        tables_text.append(f"[表格{t_idx}]")
                        for row in table:
                            cells = [str(c) if c else "" for c in row]
                            tables_text.append(" | ".join(cells))
                        tables_text.append("")
            return "\n".join(tables_text)
        except ImportError:
            # pdfplumber 未安装，跳过表格提取
            return ""
        except Exception as e:
            logger.debug(f"PDF 表格提取失败（页 {page_num}）: {e}")
            return ""

    @staticmethod
    def _parse_txt(file_path: str) -> str:
        """解析 TXT 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                return f.read()

    @staticmethod
    def _parse_md(file_path: str) -> str:
        """解析 Markdown 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            # 将 Markdown 转换为纯文本（去除标记）
            html = markdown.markdown(md_content)
            # 简单的 HTML 转文本
            import re
            text = re.sub(r'<[^>]+>', '', html)
            return text
        except Exception as e:
            logger.error(f"Markdown 解析失败：{e}")
            raise

    @staticmethod
    def _parse_docx(file_path: str) -> str:
        """解析 DOCX 文件"""
        try:
            doc = DocxDocument(file_path)
            text_parts = []
            
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            
            # 也提取表格内容
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    if row_text.strip():
                        text_parts.append(row_text)
            
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"DOCX 解析失败：{e}")
            raise

    @staticmethod
    def _parse_doc(file_path: str) -> str:
        """解析 DOC 文件（旧版 Word）"""
        try:
            import win32com.client
            from win32com.client import constants

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            
            try:
                doc = word.Documents.Open(file_path)
                try:
                    text = doc.Content.Text
                    return text.strip()
                finally:
                    doc.Close(False)
            finally:
                word.Quit()
        except ImportError:
            logger.warning("pywin32 未安装，无法解析 .doc 文件")
            return f"[DOC 文件：{os.path.basename(file_path)}]\n[无法解析 .doc 文件，请安装 pywin32 或转换为 .docx 格式]"
        except Exception as e:
            logger.error(f"DOC 解析失败：{e}")
            return f"[DOC 文件：{os.path.basename(file_path)}]\n[解析失败：{str(e)}]"
        return ""

    @staticmethod
    def _parse_image(file_path: str) -> str:
        """解析图片文件（VLM / OCR 提取文字）"""
        from config import settings

        with Image.open(file_path) as img:
            width, height = img.size
            format_name = img.format or "未知"

        base_info = f"[图片文件：{os.path.basename(file_path)}，格式：{format_name}，尺寸：{width}x{height}]"

        # 1. 优先使用 VLM（通义千问）识别图片内容
        if settings.QWEN_VL_API_KEY:
            try:
                vlm_text = DocumentParser._parse_image_with_vlm(file_path)
                if vlm_text:
                    return f"{base_info}\n[VLM 识别内容]\n{vlm_text}"
            except Exception as e:
                logger.warning(f"VLM 图片识别失败，尝试 OCR：{e}")

        # 2. 回退到 EasyOCR 本地识别
        try:
            reader = _get_ocr_reader()
            results = reader.readtext(file_path)

            if not results:
                return f"{base_info}\n[未识别到文字内容]"

            text_parts = []
            for (bbox, text, conf) in results:
                if text.strip():
                    text_parts.append(text.strip())

            extracted_text = "\n".join(text_parts)
            return f"{base_info}\n[OCR 识别内容]\n{extracted_text}"
        except Exception as e:
            logger.error(f"图片 OCR 解析失败：{e}")
            return f"{base_info}\n[图片内容识别失败：{str(e)}。如需识别图片文字，请配置 QWEN_VL_API_KEY 或安装 EasyOCR/Tesseract。]"

    @staticmethod
    def _parse_image_with_vlm(file_path: str) -> str:
        """使用通义千问 VLM 识别图片内容"""
        from config import settings
        import openai

        with open(file_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")

        client = openai.OpenAI(
            api_key=settings.QWEN_VL_API_KEY,
            base_url=settings.QWEN_VL_BASE_URL,
        )

        ext = os.path.splitext(file_path)[1].lower().replace(".", "")
        if ext not in ["png", "jpg", "jpeg", "gif", "bmp", "webp"]:
            ext = "jpeg"

        response = client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{ext};base64,{image_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": "请详细描述这张图片的内容。如果是包含文字的图片，请尽可能准确地提取所有文字。",
                        },
                    ],
                }
            ],
            max_tokens=2000,
        )

        return response.choices[0].message.content or ""
