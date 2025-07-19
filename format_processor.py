#!/usr/bin/env python3
"""
多格式输入支持模块
支持PDF、图片、Word文档等多种格式的OCR处理
"""

import os
import io
import zipfile
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass
import mimetypes

from PIL import Image, ImageSequence
import fitz  # PyMuPDF for better PDF and document handling


class FileFormat(Enum):
    """支持的文件格式"""
    PDF = "pdf"
    IMAGE = "image"
    WORD = "word"
    POWERPOINT = "powerpoint"
    UNKNOWN = "unknown"


class ImageFormat(Enum):
    """支持的图片格式"""
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    BMP = "bmp"
    WEBP = "webp"
    GIF = "gif"


@dataclass
class ProcessedFile:
    """处理后的文件信息"""
    file_path: Path
    format: FileFormat
    page_count: int
    file_size: int
    images: List[Image.Image]
    metadata: Dict[str, Any]
    temp_files: List[Path] = None  # 临时文件列表，用于清理


class FormatProcessor:
    """多格式文件处理器"""
    
    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        # PDF
        '.pdf': FileFormat.PDF,
        
        # 图片格式
        '.jpg': FileFormat.IMAGE,
        '.jpeg': FileFormat.IMAGE,
        '.png': FileFormat.IMAGE,
        '.tiff': FileFormat.IMAGE,
        '.tif': FileFormat.IMAGE,
        '.bmp': FileFormat.IMAGE,
        '.webp': FileFormat.IMAGE,
        '.gif': FileFormat.IMAGE,
        
        # Word文档
        '.docx': FileFormat.WORD,
        '.doc': FileFormat.WORD,
        
        # PowerPoint
        '.pptx': FileFormat.POWERPOINT,
        '.ppt': FileFormat.POWERPOINT,
    }
    
    # MIME类型映射
    MIME_TYPE_MAPPING = {
        'application/pdf': FileFormat.PDF,
        'image/jpeg': FileFormat.IMAGE,
        'image/png': FileFormat.IMAGE,
        'image/tiff': FileFormat.IMAGE,
        'image/bmp': FileFormat.IMAGE,
        'image/webp': FileFormat.IMAGE,
        'image/gif': FileFormat.IMAGE,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileFormat.WORD,
        'application/msword': FileFormat.WORD,
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': FileFormat.POWERPOINT,
        'application/vnd.ms-powerpoint': FileFormat.POWERPOINT,
    }
    
    def __init__(self):
        self.temp_files = []  # 跟踪临时文件
    
    def detect_format(self, file_path: Union[str, Path], file_content: bytes = None) -> FileFormat:
        """
        检测文件格式
        
        参数:
            file_path: 文件路径
            file_content: 文件内容（可选，用于更准确的检测）
        
        返回:
            FileFormat: 检测到的文件格式
        """
        file_path = Path(file_path)
        
        # 首先根据扩展名判断
        extension = file_path.suffix.lower()
        if extension in self.SUPPORTED_EXTENSIONS:
            format_by_ext = self.SUPPORTED_EXTENSIONS[extension]
        else:
            format_by_ext = FileFormat.UNKNOWN
        
        # 如果有文件内容，使用MIME类型进一步验证
        if file_content:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type in self.MIME_TYPE_MAPPING:
                format_by_mime = self.MIME_TYPE_MAPPING[mime_type]
                # 如果MIME类型和扩展名不一致，优先使用MIME类型
                if format_by_ext != format_by_mime and format_by_mime != FileFormat.UNKNOWN:
                    return format_by_mime
        
        return format_by_ext
    
    def is_supported(self, file_path: Union[str, Path]) -> bool:
        """检查文件是否支持"""
        return self.detect_format(file_path) != FileFormat.UNKNOWN
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名列表"""
        return list(self.SUPPORTED_EXTENSIONS.keys())
    
    def process_file(self, file_path: Union[str, Path], output_dir: Path = None) -> ProcessedFile:
        """
        处理文件，将其转换为可OCR的图像
        
        参数:
            file_path: 输入文件路径
            output_dir: 输出目录（可选）
        
        返回:
            ProcessedFile: 处理结果
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 检测文件格式
        file_format = self.detect_format(file_path)
        
        if file_format == FileFormat.UNKNOWN:
            raise ValueError(f"不支持的文件格式: {file_path}")
        
        # 获取文件大小
        file_size = file_path.stat().st_size
        
        # 根据格式处理文件
        if file_format == FileFormat.PDF:
            return self._process_pdf(file_path, file_size)
        elif file_format == FileFormat.IMAGE:
            return self._process_image(file_path, file_size)
        elif file_format == FileFormat.WORD:
            return self._process_word(file_path, file_size)
        elif file_format == FileFormat.POWERPOINT:
            return self._process_powerpoint(file_path, file_size)
        else:
            raise ValueError(f"暂不支持处理格式: {file_format}")
    
    def _process_pdf(self, file_path: Path, file_size: int) -> ProcessedFile:
        """处理PDF文件"""
        try:
            # 使用PyMuPDF处理PDF，比pdf2image更快更稳定
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            images = []
            
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                # 渲染为图像，300 DPI
                mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为PIL Image
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            doc.close()
            
            metadata = {
                "original_format": "PDF",
                "conversion_method": "PyMuPDF",
                "dpi": 300
            }
            
            return ProcessedFile(
                file_path=file_path,
                format=FileFormat.PDF,
                page_count=page_count,
                file_size=file_size,
                images=images,
                metadata=metadata
            )
            
        except Exception as e:
            # 如果PyMuPDF失败，回退到pdf2image
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(str(file_path), dpi=300)
                
                metadata = {
                    "original_format": "PDF",
                    "conversion_method": "pdf2image",
                    "dpi": 300
                }
                
                return ProcessedFile(
                    file_path=file_path,
                    format=FileFormat.PDF,
                    page_count=len(images),
                    file_size=file_size,
                    images=images,
                    metadata=metadata
                )
            except Exception as fallback_error:
                raise RuntimeError(f"PDF处理失败: {e}, 回退方法也失败: {fallback_error}")
    
    def _process_image(self, file_path: Path, file_size: int) -> ProcessedFile:
        """处理图片文件"""
        try:
            img = Image.open(file_path)
            images = []
            
            # 处理多帧图像（如GIF、TIFF）
            if hasattr(img, 'n_frames') and img.n_frames > 1:
                # 多帧图像
                for frame in ImageSequence.Iterator(img):
                    # 转换为RGB模式
                    if frame.mode not in ('RGB', 'L'):
                        frame = frame.convert('RGB')
                    images.append(frame.copy())
                page_count = len(images)
            else:
                # 单帧图像
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                images = [img]
                page_count = 1
            
            # 检测图像格式
            img_format = img.format.lower() if img.format else "unknown"
            
            metadata = {
                "original_format": img_format.upper(),
                "image_mode": img.mode,
                "image_size": img.size,
                "has_animation": page_count > 1
            }
            
            return ProcessedFile(
                file_path=file_path,
                format=FileFormat.IMAGE,
                page_count=page_count,
                file_size=file_size,
                images=images,
                metadata=metadata
            )
            
        except Exception as e:
            raise RuntimeError(f"图像处理失败: {e}")
    
    def _process_word(self, file_path: Path, file_size: int) -> ProcessedFile:
        """处理Word文档"""
        try:
            # 使用PyMuPDF处理Word文档
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            images = []
            
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                # 渲染为图像，300 DPI
                mat = fitz.Matrix(300/72, 300/72)
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为PIL Image
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            doc.close()
            
            metadata = {
                "original_format": "Word",
                "conversion_method": "PyMuPDF",
                "dpi": 300
            }
            
            return ProcessedFile(
                file_path=file_path,
                format=FileFormat.WORD,
                page_count=page_count,
                file_size=file_size,
                images=images,
                metadata=metadata
            )
            
        except Exception as e:
            raise RuntimeError(f"Word文档处理失败: {e}")
    
    def _process_powerpoint(self, file_path: Path, file_size: int) -> ProcessedFile:
        """处理PowerPoint文档"""
        try:
            # 使用PyMuPDF处理PowerPoint
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            images = []
            
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                # 渲染为图像，300 DPI
                mat = fitz.Matrix(300/72, 300/72)
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为PIL Image
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            doc.close()
            
            metadata = {
                "original_format": "PowerPoint",
                "conversion_method": "PyMuPDF",
                "dpi": 300
            }
            
            return ProcessedFile(
                file_path=file_path,
                format=FileFormat.POWERPOINT,
                page_count=page_count,
                file_size=file_size,
                images=images,
                metadata=metadata
            )
            
        except Exception as e:
            raise RuntimeError(f"PowerPoint文档处理失败: {e}")
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                print(f"清理临时文件失败: {temp_file}: {e}")
        self.temp_files.clear()
    
    def get_format_info(self, file_format: FileFormat) -> Dict[str, Any]:
        """获取格式信息"""
        format_info = {
            FileFormat.PDF: {
                "name": "PDF文档",
                "description": "便携式文档格式，支持多页处理",
                "extensions": [".pdf"],
                "features": ["多页支持", "矢量图形", "文本提取"]
            },
            FileFormat.IMAGE: {
                "name": "图像文件",
                "description": "各种图像格式，支持单页和多帧",
                "extensions": [".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".webp", ".gif"],
                "features": ["高质量", "多格式支持", "动画支持(GIF)"]
            },
            FileFormat.WORD: {
                "name": "Word文档",
                "description": "Microsoft Word文档格式",
                "extensions": [".docx", ".doc"],
                "features": ["文档布局", "图片提取", "格式保持"]
            },
            FileFormat.POWERPOINT: {
                "name": "PowerPoint演示文稿",
                "description": "Microsoft PowerPoint演示文稿格式",
                "extensions": [".pptx", ".ppt"],
                "features": ["幻灯片处理", "图表识别", "布局保持"]
            }
        }
        
        return format_info.get(file_format, {
            "name": "未知格式",
            "description": "不支持的文件格式",
            "extensions": [],
            "features": []
        })
    
    def batch_process(self, file_paths: List[Union[str, Path]], output_dir: Path = None) -> List[ProcessedFile]:
        """批量处理文件"""
        results = []
        
        for file_path in file_paths:
            try:
                result = self.process_file(file_path, output_dir)
                results.append(result)
            except Exception as e:
                print(f"处理文件 {file_path} 失败: {e}")
                continue
        
        return results
    
    def __del__(self):
        """析构函数，清理临时文件"""
        self.cleanup_temp_files()


def create_format_processor() -> FormatProcessor:
    """创建格式处理器的工厂函数"""
    return FormatProcessor()


def get_supported_formats() -> Dict[str, List[str]]:
    """获取支持的文件格式信息"""
    processor = FormatProcessor()
    
    formats = {}
    for ext, format_type in processor.SUPPORTED_EXTENSIONS.items():
        format_name = format_type.value
        if format_name not in formats:
            formats[format_name] = []
        formats[format_name].append(ext)
    
    return formats


def is_supported_file(file_path: Union[str, Path]) -> bool:
    """检查文件是否支持处理"""
    processor = FormatProcessor()
    return processor.is_supported(file_path)