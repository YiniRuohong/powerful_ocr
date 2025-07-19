#!/usr/bin/env python3
"""
FastAPI后端服务器 - OCR处理API
提供RESTful API接口用于前后端分离的OCR处理
"""

import os
import uuid
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import threading
import time

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 导入原有OCR功能
from main import (
    get_supported_files, get_terminology_files, load_terminology,
    get_file_page_count, ocr_manager
)
from file_splitter import PDFSplitter, SplitConfig, SplitStrategy, ChunkInfo, create_splitter_config


@dataclass
class ProcessingTask:
    """处理任务数据类"""
    task_id: str
    files: List[str]
    start_page: int
    end_page: int
    ocr_service: str
    terminology: str
    status: str  # pending, analyzing, splitting, processing, merging, completed, failed, stopped
    progress: float
    current_file: str
    current_page: int
    total_pages: int
    total_tokens: int
    ocr_tokens: int
    gemini_tokens: int
    start_time: datetime
    end_time: Optional[datetime]
    error_message: Optional[str]
    log_messages: List[Dict[str, Any]]
    # 新增分块相关字段
    chunks: List[ChunkInfo] = None
    current_chunk: int = 0
    total_chunks: int = 0
    split_config: Optional[Dict] = None
    file_analysis: Optional[Dict] = None


class SplitConfigRequest(BaseModel):
    """分割配置请求模型"""
    strategy: str = "adaptive"  # adaptive, by_pages, by_size, by_memory, intelligent
    max_pages_per_chunk: int = 50
    max_size_per_chunk_mb: int = 100
    max_memory_usage_mb: int = 512
    enable_parallel: bool = True
    preserve_structure: bool = True


class ProcessRequest(BaseModel):
    """处理请求模型"""
    filename: str
    start_page: int = 1
    end_page: int = 1
    ocr_service: str = "dashscope"
    terminology: str = ""
    # 新增分割配置
    enable_splitting: bool = True
    split_config: Optional[SplitConfigRequest] = None
    # 新增预处理配置
    enable_preprocessing: bool = True
    preprocessing_mode: str = "document"


class UploadResponse(BaseModel):
    """上传响应模型"""
    filename: str
    size: int
    message: str


class FileInfo(BaseModel):
    """文件信息模型"""
    name: str
    size: int
    pages: int
    upload_time: str


class SystemStatus(BaseModel):
    """系统状态模型"""
    available_ocr_services: Dict[str, str]
    terminology_files: List[str]
    pdf_files: List[FileInfo]  # 保持兼容性，实际包含所有支持格式


# 全局状态管理
tasks: Dict[str, ProcessingTask] = {}
task_stop_flags: Dict[str, threading.Event] = {}


# 创建FastAPI应用
app = FastAPI(
    title="OCR处理API",
    description="多引擎OCR + AI智能纠错服务",
    version="3.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务 (用于前端)
app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/")
async def read_root():
    """根路径 - 返回前端页面"""
    return FileResponse("web/index.html")


@app.get("/api/status", response_model=SystemStatus)
async def get_system_status():
    """获取系统状态"""
    try:
        # 获取可用OCR服务
        available_services = ocr_manager.get_available_services()
        ocr_services = {
            key: service.get_description() 
            for key, service in available_services.items()
        }
        
        # 获取专业词典文件
        terminology_files = get_terminology_files()
        terminology_list = [f.name for f in terminology_files]
        
        # 获取支持的文件信息
        input_files = get_supported_files()
        file_info_list = []
        
        for input_file in input_files:
            try:
                pages = get_file_page_count(input_file)
                size = input_file.stat().st_size
                upload_time = datetime.fromtimestamp(input_file.stat().st_mtime).isoformat()
                
                file_info_list.append(FileInfo(
                    name=input_file.name,
                    size=size,
                    pages=pages,
                    upload_time=upload_time
                ))
            except Exception as e:
                print(f"Error reading file info for {input_file}: {e}")
                continue
        
        return SystemStatus(
            available_ocr_services=ocr_services,
            terminology_files=terminology_list,
            pdf_files=file_info_list
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传支持的文件格式 - 支持大文件"""
    from format_processor import FormatProcessor
    
    # 检查文件格式
    processor = FormatProcessor()
    if not processor.is_supported(file.filename):
        supported_exts = processor.get_supported_extensions()
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件格式。支持的格式: {', '.join(supported_exts)}"
        )
    
    # 检查文件大小 (限制500MB)
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    
    try:
        # 确保input目录存在
        input_dir = Path("input")
        input_dir.mkdir(exist_ok=True)
        
        # 为避免文件名冲突，添加时间戳
        timestamp = int(time.time())
        file_path = input_dir / f"{timestamp}_{file.filename}"
        
        # 分块读取和保存文件以支持大文件
        total_size = 0
        chunk_size = 8192  # 8KB chunks
        
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                
                total_size += len(chunk)
                
                # 检查文件大小
                if total_size > MAX_FILE_SIZE:
                    f.close()
                    file_path.unlink()  # 删除部分上传的文件
                    raise HTTPException(status_code=413, detail="文件过大，最大支持500MB")
                
                f.write(chunk)
        
        # 验证文件完整性
        try:
            from main import get_file_page_count
            pages = get_file_page_count(file_path)
            if pages <= 0:
                file_path.unlink()
                raise HTTPException(status_code=400, detail="文件损坏或为空")
        except Exception as e:
            file_path.unlink()
            raise HTTPException(status_code=400, detail="文件无效或格式不支持")
        
        return UploadResponse(
            filename=file_path.name,  # 返回带时间戳的文件名
            size=total_size,
            message="文件上传成功"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@app.get("/api/file/{filename}")
async def get_file_info(filename: str):
    """获取指定文件信息"""
    try:
        input_dir = Path("input")
        file_path = input_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        pages = get_file_page_count(file_path)
        size = file_path.stat().st_size
        upload_time = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        
        return {
            "name": file_path.name,
            "size": size,
            "pages": pages,
            "upload_time": upload_time
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件信息失败: {str(e)}")


@app.get("/api/analyze/{filename}")
async def analyze_file(filename: str):
    """分析PDF文件特征和分割建议"""
    try:
        input_dir = Path("input")
        file_path = input_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 创建分割器并分析文件
        splitter = PDFSplitter()
        analysis = splitter.analyze_pdf(file_path)
        
        # 创建分割计划
        split_plan = splitter.create_split_plan(file_path, analysis)
        
        # 格式化返回结果
        result = {
            "filename": filename,
            "analysis": analysis,
            "split_plan": [
                {
                    "chunk_id": chunk.chunk_id,
                    "start_page": chunk.start_page,
                    "end_page": chunk.end_page,
                    "page_count": chunk.page_count,
                    "estimated_size_mb": round(chunk.estimated_size_mb, 2)
                }
                for chunk in split_plan
            ],
            "needs_splitting": analysis["needs_splitting"],
            "recommended_strategy": analysis["recommended_strategy"].value,
            "total_chunks": len(split_plan)
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件分析失败: {str(e)}")


@app.post("/api/process")
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    """开始处理PDF文件"""
    try:
        # 验证文件存在
        input_dir = Path("input")
        file_path = input_dir / request.filename
        
        if not file_path.exists():
            raise HTTPException(status_code=400, detail=f"文件不存在: {request.filename}")
        
        # 验证OCR服务
        available_services = ocr_manager.get_available_services()
        if request.ocr_service not in available_services:
            raise HTTPException(status_code=400, detail=f"OCR服务不可用: {request.ocr_service}")
        
        # 创建任务ID
        task_id = str(uuid.uuid4())
        
        # 加载专业词典
        terminology_terms = ""
        if request.terminology:
            terminology_files = get_terminology_files()
            for term_file in terminology_files:
                if term_file.name == request.terminology:
                    terminology_terms = load_terminology(term_file)
                    break
        
        # 创建分割配置
        split_config_dict = None
        if request.enable_splitting and request.split_config:
            split_config_dict = {
                "strategy": request.split_config.strategy,
                "max_pages_per_chunk": request.split_config.max_pages_per_chunk,
                "max_size_per_chunk_mb": request.split_config.max_size_per_chunk_mb,
                "max_memory_usage_mb": request.split_config.max_memory_usage_mb,
                "enable_parallel": request.split_config.enable_parallel,
                "preserve_structure": request.split_config.preserve_structure
            }
        
        # 创建预处理配置
        preprocessing_config = None
        if request.enable_preprocessing:
            from image_preprocessor import create_preprocessor_config
            preprocessing_config = create_preprocessor_config(mode=request.preprocessing_mode)
        
        # 创建处理任务
        task = ProcessingTask(
            task_id=task_id,
            files=[request.filename],  # 转为列表以保持兼容性
            start_page=request.start_page,
            end_page=request.end_page,
            ocr_service=request.ocr_service,
            terminology=request.terminology,
            status="pending",
            progress=0.0,
            current_file="",
            current_page=0,
            total_pages=0,
            total_tokens=0,
            ocr_tokens=0,
            gemini_tokens=0,
            start_time=datetime.now(),
            end_time=None,
            error_message=None,
            log_messages=[],
            # 新增字段
            chunks=[],
            current_chunk=0,
            total_chunks=0,
            split_config=split_config_dict,
            file_analysis=None
        )
        
        # 保存任务
        tasks[task_id] = task
        task_stop_flags[task_id] = threading.Event()
        
        # 启动后台处理
        background_tasks.add_task(
            process_file_background,
            task_id,
            request.filename,
            request.start_page,
            request.end_page,
            terminology_terms,
            request.ocr_service,
            request.enable_splitting,
            preprocessing_config
        )
        
        return {"task_id": task_id, "message": "处理任务已启动"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动处理失败: {str(e)}")


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    """获取处理进度"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    return {
        "task_id": task_id,
        "status": task.status,
        "progress": task.progress,
        "current_file": task.current_file,
        "current_page": task.current_page,
        "total_pages": task.total_pages,
        "total_tokens": task.total_tokens,
        "ocr_tokens": task.ocr_tokens,
        "gemini_tokens": task.gemini_tokens,
        "start_time": task.start_time.isoformat(),
        "end_time": task.end_time.isoformat() if task.end_time else None,
        "error_message": task.error_message,
        "log_messages": task.log_messages[-50:],  # 只返回最近50条日志
        # 新增分块信息
        "current_chunk": task.current_chunk,
        "total_chunks": task.total_chunks,
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "start_page": chunk.start_page,
                "end_page": chunk.end_page,
                "page_count": chunk.page_count,
                "status": chunk.status
            }
            for chunk in (task.chunks or [])
        ] if task.chunks else [],
        "file_analysis": task.file_analysis,
        "split_config": task.split_config
    }


@app.post("/api/stop/{task_id}")
async def stop_processing(task_id: str):
    """停止处理任务"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task_id in task_stop_flags:
        task_stop_flags[task_id].set()
    
    task = tasks[task_id]
    if task.status == "processing":
        task.status = "stopped"
        task.end_time = datetime.now()
        add_log_message(task_id, "⏹️ 处理已停止", "warning")
    
    return {"message": "停止信号已发送"}


@app.get("/api/download/{filename}")
async def download_result(filename: str):
    """下载处理结果"""
    output_dir = Path("ocr_output")
    file_path = output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 根据文件扩展名设置正确的MIME类型
    if filename.endswith('.md'):
        media_type = 'text/markdown'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type
    )


@app.get("/api/results")
async def list_results():
    """获取处理结果列表"""
    try:
        output_dir = Path("ocr_output")
        if not output_dir.exists():
            return {"files": []}
        
        result_files = []
        for file_path in output_dir.glob("*.md"):
            try:
                size = file_path.stat().st_size
                modified_time = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                
                result_files.append({
                    "name": file_path.name,
                    "size": size,
                    "modified_time": modified_time
                })
            except Exception as e:
                print(f"Error reading result file info for {file_path}: {e}")
                continue
        
        return {"files": result_files}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取结果列表失败: {str(e)}")


def add_log_message(task_id: str, message: str, level: str = "info"):
    """添加日志消息"""
    if task_id in tasks:
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "message": message,
            "level": level
        }
        tasks[task_id].log_messages.append(log_entry)
        
        # 限制日志数量
        if len(tasks[task_id].log_messages) > 1000:
            tasks[task_id].log_messages = tasks[task_id].log_messages[-500:]


def create_progress_callback(task_id: str):
    """创建进度回调函数"""
    def callback(msg_type, data, **kwargs):
        if task_id not in tasks:
            return
        
        task = tasks[task_id]
        
        if msg_type == 'page_start':
            page_idx, total_pages = data
            task.current_page = page_idx + 1
            task.total_pages = total_pages
            add_log_message(task_id, f"开始处理第 {page_idx + 1} 页", "info")
            
        elif msg_type == 'chunk_start':
            chunk_idx, total_chunks = data
            task.current_chunk = chunk_idx + 1
            task.total_chunks = total_chunks
            add_log_message(task_id, f"开始处理分块 {chunk_idx + 1}/{total_chunks}", "info")
            
        elif msg_type == 'chunk_complete':
            chunk_idx = data
            add_log_message(task_id, f"✅ 分块 {chunk_idx + 1} 处理完成", "success")
            
        elif msg_type == 'ocr_token':
            tokens = data
            token_count = tokens.get('total_tokens', 0)
            task.ocr_tokens += token_count
            task.total_tokens += token_count
            
            input_tokens = tokens.get('input_tokens', 0)
            output_tokens = tokens.get('output_tokens', 0)
            add_log_message(task_id, f"📊 OCR Token: {token_count:,} (输入: {input_tokens:,}, 输出: {output_tokens:,})", "token")
            
        elif msg_type == 'gemini_token':
            tokens = data
            token_count = tokens.get('total_tokens', 0)
            task.gemini_tokens += token_count
            task.total_tokens += token_count
            
            input_tokens = tokens.get('input_tokens', 0)
            output_tokens = tokens.get('output_tokens', 0)
            add_log_message(task_id, f"📊 Gemini Token: {token_count:,} (输入: {input_tokens:,}, 输出: {output_tokens:,})", "token")
            
        elif msg_type == 'page_complete':
            page_idx = data
            add_log_message(task_id, f"✅ 第 {page_idx + 1} 页处理完成", "success")
    
    return callback


async def process_file_background(task_id: str, filename: str, start_page: int, end_page: int, terminology_terms: str, ocr_service: str, enable_splitting: bool = True, preprocessing_config = None):
    """后台处理单个文件 - 支持分块处理"""
    try:
        task = tasks[task_id]
        task.status = "analyzing"
        add_log_message(task_id, f"🚀 开始分析文件: {filename}", "info")
        
        # 获取PDF文件路径
        input_dir = Path("input")
        pdf_path = input_dir / filename
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"文件不存在: {filename}")
        
        progress_callback = create_progress_callback(task_id)
        
        # 更新当前文件
        task.current_file = pdf_path.name
        
        # 检查是否需要分割处理
        if enable_splitting and task.split_config:
            await process_with_splitting(task_id, pdf_path, start_page, end_page, terminology_terms, ocr_service, progress_callback, preprocessing_config)
        else:
            await process_without_splitting(task_id, pdf_path, start_page, end_page, terminology_terms, ocr_service, progress_callback, preprocessing_config)
        
    except Exception as e:
        task = tasks[task_id]
        task.status = "failed"
        task.error_message = str(e)
        task.end_time = datetime.now()
        add_log_message(task_id, f"❌ 处理失败: {str(e)}", "error")


async def process_without_splitting(task_id: str, pdf_path: Path, start_page: int, end_page: int, terminology_terms: str, ocr_service: str, progress_callback, preprocessing_config = None):
    """不分割的传统处理方式"""
    task = tasks[task_id]
    task.status = "processing"
    add_log_message(task_id, f"正在处理: {pdf_path.name}", "info")
    
    # 导入处理函数
    from main import process_single_file_with_progress_callback
    
    # 检查停止标志
    if task_id in task_stop_flags and task_stop_flags[task_id].is_set():
        task.status = "stopped"
        add_log_message(task_id, "⏹️ 处理已停止", "warning")
        return
    
    # 重置页面Token统计
    task.current_page = 0
    task.total_pages = 0
    
    try:
        # 处理文件
        result = process_single_file_with_progress_callback(
            pdf_path, start_page, end_page,
            terminology_terms, ocr_service,
            progress_callback, preprocessing_config
        )
        add_log_message(task_id, f"✅ {pdf_path.name} 处理完成", "success")
        
    except Exception as e:
        add_log_message(task_id, f"❌ {pdf_path.name} 处理失败: {str(e)}", "error")
        raise
    
    # 处理完成
    if task.status == "processing":
        task.status = "completed"
        task.progress = 100.0
        add_log_message(task_id, "🎉 文件处理完成！", "success")
    
    task.end_time = datetime.now()


async def process_with_splitting(task_id: str, pdf_path: Path, start_page: int, end_page: int, terminology_terms: str, ocr_service: str, progress_callback, preprocessing_config = None):
    """分块处理方式"""
    task = tasks[task_id]
    
    try:
        # 创建分割器配置
        split_config = task.split_config
        config = SplitConfig(
            strategy=SplitStrategy(split_config["strategy"]),
            max_pages_per_chunk=split_config["max_pages_per_chunk"],
            max_size_per_chunk_mb=split_config["max_size_per_chunk_mb"],
            max_memory_usage_mb=split_config["max_memory_usage_mb"],
            parallel_processing=split_config["enable_parallel"],
            preserve_structure=split_config["preserve_structure"]
        )
        
        # 创建分割器
        splitter = PDFSplitter(config)
        
        # 分析文件
        add_log_message(task_id, "🔍 分析PDF文件特征...", "info")
        analysis = splitter.analyze_pdf(pdf_path)
        task.file_analysis = analysis
        
        # 创建分割计划
        add_log_message(task_id, "📋 创建分割计划...", "info")
        chunks = splitter.create_split_plan(pdf_path, analysis)
        
        # 过滤页面范围
        filtered_chunks = []
        for chunk in chunks:
            # 计算与请求页面范围的交集
            chunk_start = max(chunk.start_page, start_page)
            chunk_end = min(chunk.end_page, end_page)
            
            if chunk_start <= chunk_end:
                # 创建新的chunk信息
                new_chunk = ChunkInfo(
                    chunk_id=chunk.chunk_id,
                    start_page=chunk_start,
                    end_page=chunk_end,
                    page_count=chunk_end - chunk_start + 1,
                    estimated_size_mb=chunk.estimated_size_mb * (chunk_end - chunk_start + 1) / chunk.page_count
                )
                filtered_chunks.append(new_chunk)
        
        task.chunks = filtered_chunks
        task.total_chunks = len(filtered_chunks)
        
        if not filtered_chunks:
            raise ValueError("没有需要处理的页面")
        
        add_log_message(task_id, f"📊 分割计划: {len(filtered_chunks)} 个分块", "info")
        
        # 分割PDF文件
        if analysis["needs_splitting"]:
            task.status = "splitting"
            add_log_message(task_id, "✂️ 分割PDF文件...", "info")
            chunks_with_files = splitter.split_pdf_file(pdf_path, filtered_chunks)
            task.chunks = chunks_with_files
        else:
            add_log_message(task_id, "📄 文件无需分割，直接处理", "info")
            for chunk in filtered_chunks:
                chunk.file_path = pdf_path
                chunk.status = "ready"
        
        # 处理分块
        task.status = "processing"
        await process_chunks(task_id, task.chunks, terminology_terms, ocr_service, progress_callback, splitter, preprocessing_config)
        
    except Exception as e:
        add_log_message(task_id, f"❌ 分块处理失败: {str(e)}", "error")
        raise


async def process_chunks(task_id: str, chunks: List[ChunkInfo], terminology_terms: str, ocr_service: str, progress_callback, splitter: PDFSplitter, preprocessing_config = None):
    """处理所有分块"""
    task = tasks[task_id]
    
    # 导入处理函数
    from main import process_single_file_with_progress_callback
    
    successful_chunks = []
    failed_chunks = []
    
    for i, chunk in enumerate(chunks):
        # 检查停止标志
        if task_id in task_stop_flags and task_stop_flags[task_id].is_set():
            task.status = "stopped"
            add_log_message(task_id, "⏹️ 处理已停止", "warning")
            return
        
        # 更新进度
        task.current_chunk = i + 1
        progress_callback('chunk_start', (i, len(chunks)))
        
        chunk.status = "processing"
        
        try:
            # 处理单个分块
            add_log_message(task_id, f"🔄 处理分块 {chunk.chunk_id} (页面 {chunk.start_page}-{chunk.end_page})", "info")
            
            result = process_single_file_with_progress_callback(
                chunk.file_path, 
                chunk.start_page if chunk.file_path != chunks[0].file_path or len(chunks) == 1 else 1,  # 如果是分割文件，从第1页开始
                chunk.end_page if chunk.file_path != chunks[0].file_path or len(chunks) == 1 else chunk.page_count,
                terminology_terms, 
                ocr_service,
                progress_callback, preprocessing_config
            )
            
            chunk.status = "completed"
            chunk.ocr_result = result  # 这里需要从处理结果中提取文本
            successful_chunks.append(chunk)
            
            progress_callback('chunk_complete', i)
            add_log_message(task_id, f"✅ 分块 {chunk.chunk_id} 处理完成", "success")
            
        except Exception as e:
            chunk.status = "failed"
            chunk.error_message = str(e)
            failed_chunks.append(chunk)
            add_log_message(task_id, f"❌ 分块 {chunk.chunk_id} 处理失败: {str(e)}", "error")
        
        # 更新总进度
        task.progress = ((i + 1) / len(chunks)) * 90  # 90%用于处理，10%用于合并
    
    # 合并结果
    if successful_chunks:
        task.status = "merging"
        add_log_message(task_id, "🔗 合并处理结果...", "info")
        
        try:
            # 读取OCR结果文件
            for chunk in successful_chunks:
                if not chunk.ocr_result:
                    # 从输出文件中读取结果
                    output_dir = Path("ocr_output")
                    if chunk.file_path:
                        base_name = chunk.file_path.stem
                        combined_file = output_dir / f"{base_name}_combined.md"
                        if combined_file.exists():
                            chunk.ocr_result = combined_file.read_text(encoding='utf-8')
            
            # 合并结果
            merged_result = splitter.merge_ocr_results(successful_chunks)
            
            # 保存合并结果
            output_dir = Path("ocr_output")
            output_dir.mkdir(exist_ok=True)
            final_output = output_dir / f"{chunks[0].file_path.stem}_merged_combined.md"
            final_output.write_text(merged_result, encoding='utf-8')
            
            add_log_message(task_id, f"📁 合并结果已保存: {final_output.name}", "success")
            
        except Exception as e:
            add_log_message(task_id, f"⚠️ 结果合并失败，但分块处理已完成: {str(e)}", "warning")
    
    # 清理临时文件
    try:
        splitter.cleanup_chunks(chunks)
    except Exception as e:
        add_log_message(task_id, f"⚠️ 清理临时文件失败: {str(e)}", "warning")
    
    # 完成处理
    if task.status == "merging":
        task.status = "completed"
        task.progress = 100.0
        add_log_message(task_id, f"🎉 文件处理完成！成功: {len(successful_chunks)}, 失败: {len(failed_chunks)}", "success")
    
    task.end_time = datetime.now()


if __name__ == "__main__":
    # 确保必要目录存在
    Path("input").mkdir(exist_ok=True)
    Path("ocr_output").mkdir(exist_ok=True)
    Path("web").mkdir(exist_ok=True)
    
    print("🚀 启动OCR API服务器...")
    print("📍 API文档: http://localhost:8000/docs")
    print("🌐 Web界面: http://localhost:8000")
    
    uvicorn.run(
        "backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )