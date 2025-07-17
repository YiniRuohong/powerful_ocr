#!/usr/bin/env python3
"""
PDF文件分割器 - 支持大文件自动分割处理
提供多种分割策略和智能合并功能
"""

import os
import math
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

try:
    import pypdf
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("❌ 需要安装pypdf: uv add pypdf")
    raise


class SplitStrategy(Enum):
    """分割策略枚举"""
    BY_PAGES = "by_pages"           # 按页数分割
    BY_SIZE = "by_size"             # 按文件大小分割
    BY_MEMORY = "by_memory"         # 按内存限制分割
    INTELLIGENT = "intelligent"     # 智能分割（基于内容结构）
    ADAPTIVE = "adaptive"           # 自适应分割（综合策略）


@dataclass
class SplitConfig:
    """分割配置"""
    strategy: SplitStrategy = SplitStrategy.ADAPTIVE
    max_pages_per_chunk: int = 50           # 每个分块最大页数
    max_size_per_chunk_mb: int = 100        # 每个分块最大大小(MB)
    max_memory_usage_mb: int = 512          # 最大内存使用(MB)
    min_pages_per_chunk: int = 5            # 最小页数（避免过度分割）
    overlap_pages: int = 0                  # 页面重叠数（用于上下文保持）
    preserve_structure: bool = True         # 是否保持文档结构
    parallel_processing: bool = True        # 是否并行处理
    max_parallel_chunks: int = 4            # 最大并行处理数


@dataclass 
class ChunkInfo:
    """分块信息"""
    chunk_id: str
    start_page: int
    end_page: int
    page_count: int
    estimated_size_mb: float
    file_path: Optional[Path] = None
    status: str = "pending"  # pending, processing, completed, failed
    ocr_result: Optional[str] = None
    error_message: Optional[str] = None


class PDFSplitter:
    """PDF文件分割器"""
    
    def __init__(self, config: Optional[SplitConfig] = None):
        self.config = config or SplitConfig()
        self.logger = logging.getLogger(__name__)
        
    def analyze_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """分析PDF文件特征"""
        try:
            reader = PdfReader(pdf_path)
            file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
            page_count = len(reader.pages)
            
            # 估算平均页面大小
            avg_page_size_mb = file_size_mb / page_count if page_count > 0 else 0
            
            # 检查是否包含图片（简单检测）
            has_images = self._detect_images(reader)
            
            # 估算内存使用
            estimated_memory_mb = self._estimate_memory_usage(reader)
            
            analysis = {
                "file_size_mb": file_size_mb,
                "page_count": page_count,
                "avg_page_size_mb": avg_page_size_mb,
                "has_images": has_images,
                "estimated_memory_mb": estimated_memory_mb,
                "needs_splitting": self._should_split(file_size_mb, page_count, estimated_memory_mb),
                "recommended_strategy": self._recommend_strategy(file_size_mb, page_count, estimated_memory_mb, has_images)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"PDF分析失败: {e}")
            raise
    
    def _detect_images(self, reader: PdfReader) -> bool:
        """检测PDF是否包含大量图片"""
        try:
            # 检查前几页是否包含图片
            sample_pages = min(5, len(reader.pages))
            image_count = 0
            
            for i in range(sample_pages):
                page = reader.pages[i]
                if '/XObject' in page['/Resources']:
                    xobjects = page['/Resources']['/XObject']
                    for obj in xobjects:
                        if xobjects[obj]['/Subtype'] == '/Image':
                            image_count += 1
            
            # 如果平均每页超过2张图片，认为是图片密集型PDF
            return (image_count / sample_pages) > 2
            
        except:
            return False
    
    def _estimate_memory_usage(self, reader: PdfReader) -> float:
        """估算内存使用量(MB)"""
        try:
            # 基于页数和复杂度的简单估算
            page_count = len(reader.pages)
            
            # 基础内存消耗
            base_memory = 50  # MB
            
            # 每页内存消耗估算
            memory_per_page = 2  # MB (保守估计)
            
            total_memory = base_memory + (page_count * memory_per_page)
            
            return min(total_memory, 2048)  # 最大2GB
            
        except:
            return 200  # 默认估算
    
    def _should_split(self, file_size_mb: float, page_count: int, estimated_memory_mb: float) -> bool:
        """判断是否需要分割"""
        return (
            file_size_mb > self.config.max_size_per_chunk_mb or
            page_count > self.config.max_pages_per_chunk or
            estimated_memory_mb > self.config.max_memory_usage_mb
        )
    
    def _recommend_strategy(self, file_size_mb: float, page_count: int, 
                          estimated_memory_mb: float, has_images: bool) -> SplitStrategy:
        """推荐分割策略"""
        if estimated_memory_mb > self.config.max_memory_usage_mb * 2:
            return SplitStrategy.BY_MEMORY
        elif has_images:
            return SplitStrategy.BY_SIZE
        elif page_count > 200:
            return SplitStrategy.BY_PAGES
        else:
            return SplitStrategy.ADAPTIVE
    
    def create_split_plan(self, pdf_path: Path, analysis: Optional[Dict] = None) -> List[ChunkInfo]:
        """创建分割计划"""
        if analysis is None:
            analysis = self.analyze_pdf(pdf_path)
        
        if not analysis["needs_splitting"]:
            # 不需要分割，返回单个块
            return [ChunkInfo(
                chunk_id="chunk_001",
                start_page=1,
                end_page=analysis["page_count"],
                page_count=analysis["page_count"],
                estimated_size_mb=analysis["file_size_mb"]
            )]
        
        # 根据策略创建分割计划
        strategy = analysis.get("recommended_strategy", self.config.strategy)
        
        if strategy == SplitStrategy.BY_PAGES:
            return self._split_by_pages(analysis)
        elif strategy == SplitStrategy.BY_SIZE:
            return self._split_by_size(analysis)
        elif strategy == SplitStrategy.BY_MEMORY:
            return self._split_by_memory(analysis)
        elif strategy == SplitStrategy.INTELLIGENT:
            return self._split_intelligently(pdf_path, analysis)
        else:  # ADAPTIVE
            return self._split_adaptively(analysis)
    
    def _split_by_pages(self, analysis: Dict) -> List[ChunkInfo]:
        """按页数分割"""
        page_count = analysis["page_count"]
        max_pages = self.config.max_pages_per_chunk
        avg_page_size = analysis["avg_page_size_mb"]
        
        chunks = []
        start_page = 1
        chunk_id = 1
        
        while start_page <= page_count:
            end_page = min(start_page + max_pages - 1, page_count)
            actual_pages = end_page - start_page + 1
            
            chunks.append(ChunkInfo(
                chunk_id=f"chunk_{chunk_id:03d}",
                start_page=start_page,
                end_page=end_page,
                page_count=actual_pages,
                estimated_size_mb=actual_pages * avg_page_size
            ))
            
            start_page = end_page + 1 - self.config.overlap_pages
            chunk_id += 1
        
        return chunks
    
    def _split_by_size(self, analysis: Dict) -> List[ChunkInfo]:
        """按文件大小分割"""
        page_count = analysis["page_count"]
        avg_page_size = analysis["avg_page_size_mb"]
        max_size = self.config.max_size_per_chunk_mb
        
        # 计算每个块的页数
        pages_per_chunk = max(
            self.config.min_pages_per_chunk,
            int(max_size / avg_page_size) if avg_page_size > 0 else self.config.max_pages_per_chunk
        )
        
        chunks = []
        start_page = 1
        chunk_id = 1
        
        while start_page <= page_count:
            end_page = min(start_page + pages_per_chunk - 1, page_count)
            actual_pages = end_page - start_page + 1
            
            chunks.append(ChunkInfo(
                chunk_id=f"chunk_{chunk_id:03d}",
                start_page=start_page,
                end_page=end_page,
                page_count=actual_pages,
                estimated_size_mb=actual_pages * avg_page_size
            ))
            
            start_page = end_page + 1 - self.config.overlap_pages
            chunk_id += 1
        
        return chunks
    
    def _split_by_memory(self, analysis: Dict) -> List[ChunkInfo]:
        """按内存限制分割"""
        page_count = analysis["page_count"]
        estimated_memory = analysis["estimated_memory_mb"]
        max_memory = self.config.max_memory_usage_mb
        
        # 计算内存安全的页数
        memory_per_page = estimated_memory / page_count if page_count > 0 else 2
        safe_pages = max(
            self.config.min_pages_per_chunk,
            int(max_memory / memory_per_page) if memory_per_page > 0 else 10
        )
        
        chunks = []
        start_page = 1
        chunk_id = 1
        
        while start_page <= page_count:
            end_page = min(start_page + safe_pages - 1, page_count)
            actual_pages = end_page - start_page + 1
            
            chunks.append(ChunkInfo(
                chunk_id=f"chunk_{chunk_id:03d}",
                start_page=start_page,
                end_page=end_page,
                page_count=actual_pages,
                estimated_size_mb=actual_pages * analysis["avg_page_size_mb"]
            ))
            
            start_page = end_page + 1 - self.config.overlap_pages
            chunk_id += 1
        
        return chunks
    
    def _split_intelligently(self, pdf_path: Path, analysis: Dict) -> List[ChunkInfo]:
        """智能分割（基于文档结构）"""
        # 简化版本：基于页面内容变化点进行分割
        # 实际实现需要更复杂的文档结构分析
        return self._split_adaptively(analysis)
    
    def _split_adaptively(self, analysis: Dict) -> List[ChunkInfo]:
        """自适应分割（综合策略）"""
        page_count = analysis["page_count"]
        file_size_mb = analysis["file_size_mb"]
        has_images = analysis["has_images"]
        
        # 根据文件特征选择最优策略
        if has_images and file_size_mb > 200:
            # 图片密集型大文件：优先按大小分割
            return self._split_by_size(analysis)
        elif page_count > 100:
            # 页数较多：按页数分割
            return self._split_by_pages(analysis)
        else:
            # 默认按内存分割
            return self._split_by_memory(analysis)
    
    def split_pdf_file(self, pdf_path: Path, chunks: List[ChunkInfo], 
                       output_dir: Optional[Path] = None) -> List[ChunkInfo]:
        """实际分割PDF文件"""
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="pdf_chunks_"))
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            reader = PdfReader(pdf_path)
            
            for chunk in chunks:
                if chunk.page_count == len(reader.pages) and len(chunks) == 1:
                    # 单个块且是完整文件，直接使用原文件
                    chunk.file_path = pdf_path
                    chunk.status = "ready"
                    continue
                
                # 创建分块文件
                writer = PdfWriter()
                
                # 添加指定范围的页面
                for page_num in range(chunk.start_page - 1, chunk.end_page):
                    if page_num < len(reader.pages):
                        writer.add_page(reader.pages[page_num])
                
                # 保存分块文件
                chunk_file = output_dir / f"{pdf_path.stem}_{chunk.chunk_id}.pdf"
                with open(chunk_file, 'wb') as output_file:
                    writer.write(output_file)
                
                chunk.file_path = chunk_file
                chunk.status = "ready"
                
                # 更新实际文件大小
                chunk.estimated_size_mb = chunk_file.stat().st_size / (1024 * 1024)
            
            return chunks
            
        except Exception as e:
            self.logger.error(f"PDF分割失败: {e}")
            raise
    
    def merge_ocr_results(self, chunks: List[ChunkInfo], 
                         preserve_structure: bool = True) -> str:
        """合并OCR结果"""
        if not chunks:
            return ""
        
        # 按chunk_id排序确保顺序正确
        sorted_chunks = sorted(chunks, key=lambda x: x.chunk_id)
        
        # 收集所有成功的OCR结果
        successful_results = []
        failed_chunks = []
        
        for chunk in sorted_chunks:
            if chunk.status == "completed" and chunk.ocr_result:
                successful_results.append(chunk.ocr_result)
            elif chunk.status == "failed":
                failed_chunks.append(chunk.chunk_id)
        
        if not successful_results:
            raise ValueError("没有成功的OCR结果可以合并")
        
        # 智能合并结果
        if preserve_structure:
            merged_content = self._intelligent_merge(successful_results, failed_chunks)
        else:
            merged_content = "\n\n".join(successful_results)
        
        return merged_content
    
    def _intelligent_merge(self, results: List[str], failed_chunks: List[str]) -> str:
        """智能合并OCR结果"""
        merged_sections = []
        
        for i, result in enumerate(results):
            # 添加分段标识
            if len(results) > 1:
                section_header = f"\n\n---\n\n# 文档段落 {i + 1}\n\n"
                merged_sections.append(section_header + result.strip())
            else:
                merged_sections.append(result.strip())
        
        merged_content = "".join(merged_sections)
        
        # 添加处理摘要
        if failed_chunks:
            summary = f"\n\n---\n\n## 处理摘要\n\n"
            summary += f"- 成功处理段落: {len(results)}\n"
            summary += f"- 失败段落: {len(failed_chunks)}\n"
            if failed_chunks:
                summary += f"- 失败的段落ID: {', '.join(failed_chunks)}\n"
            
            merged_content += summary
        
        return merged_content
    
    def cleanup_chunks(self, chunks: List[ChunkInfo]):
        """清理临时分块文件"""
        for chunk in chunks:
            if chunk.file_path and chunk.file_path.exists():
                try:
                    # 只删除临时文件，不删除原始文件
                    if "chunks_" in str(chunk.file_path.parent):
                        chunk.file_path.unlink()
                except Exception as e:
                    self.logger.warning(f"清理临时文件失败: {e}")
        
        # 清理临时目录
        for chunk in chunks:
            if chunk.file_path:
                temp_dir = chunk.file_path.parent
                if "chunks_" in str(temp_dir) and temp_dir.exists():
                    try:
                        temp_dir.rmdir()
                        break  # 只需要删除一次
                    except:
                        pass


def create_splitter_config(
    max_file_size_mb: int = 500,
    max_pages_per_chunk: int = 50,
    max_memory_mb: int = 512,
    enable_parallel: bool = True
) -> SplitConfig:
    """创建分割器配置的便捷函数"""
    return SplitConfig(
        strategy=SplitStrategy.ADAPTIVE,
        max_pages_per_chunk=max_pages_per_chunk,
        max_size_per_chunk_mb=max_file_size_mb // 5,  # 分成大约5个块
        max_memory_usage_mb=max_memory_mb,
        parallel_processing=enable_parallel,
        max_parallel_chunks=min(4, os.cpu_count() or 2)
    )


# 使用示例
if __name__ == "__main__":
    # 创建分割器
    config = create_splitter_config(max_file_size_mb=500)
    splitter = PDFSplitter(config)
    
    # 分析文件
    pdf_path = Path("example.pdf")
    if pdf_path.exists():
        analysis = splitter.analyze_pdf(pdf_path)
        print(f"文件分析结果: {analysis}")
        
        # 创建分割计划
        chunks = splitter.create_split_plan(pdf_path, analysis)
        print(f"分割计划: {len(chunks)} 个分块")
        
        for chunk in chunks:
            print(f"  {chunk.chunk_id}: 页面 {chunk.start_page}-{chunk.end_page} ({chunk.page_count} 页)")