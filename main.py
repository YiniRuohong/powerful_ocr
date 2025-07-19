#!/usr/bin/env python3
"""
main.py – OCR a (range of) PDF pages using Alibaba DashScope's
Qwen-VL OCR model via the OpenAI‑compatible endpoint.
Then use third-party Gemini service for text correction.

Env vars expected in .env (same directory):
  DASHSCOPE_API_KEY   – your DashScope (Bailian) API key
  GEMINI_API_KEY      – your Gemini API key
  GEMINI_BASE_URL     – third-party Gemini service URL
"""

import base64
import io
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict, Any, Callable
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from openai import OpenAI
from pdf2image import convert_from_path, exceptions as pdf_exc
from tqdm import tqdm
import pypdf

# ---------- 1. Dependency checking ----------
def check_dependencies():
    """检查所有依赖项"""
    missing_deps = []
    
    # 检查必要的包
    try:
        import pdf2image
    except ImportError:
        missing_deps.append("pdf2image 包未安装 (运行: uv add pdf2image)")
    
    try:
        import pypdf
    except ImportError:
        missing_deps.append("pypdf 包未安装 (运行: uv add pypdf)")
    
    try:
        import openai
    except ImportError:
        missing_deps.append("openai 包未安装 (运行: uv add openai)")
    
    try:
        import google.generativeai
    except ImportError:
        missing_deps.append("google-generativeai 包未安装 (运行: uv add google-generativeai)")
    
    try:
        import tqdm
    except ImportError:
        missing_deps.append("tqdm 包未安装 (运行: uv add tqdm)")
    
    try:
        import dotenv
    except ImportError:
        missing_deps.append("python-dotenv 包未安装 (运行: uv add python-dotenv)")
    
    # 检查poppler
    try:
        from pdf2image import convert_from_path
        # 创建一个临时的小PDF来测试poppler
        test_path = Path(__file__).parent / "test_dummy.pdf"
        if not test_path.exists():
            # 如果没有测试文件，只检查导入是否成功
            pass
    except Exception as e:
        if "poppler" in str(e).lower() or "pdftoppm" in str(e).lower():
            missing_deps.append("Poppler 未安装 (macOS: brew install poppler, Ubuntu: sudo apt install poppler-utils)")
    
    return missing_deps

def check_env_vars():
    """检查环境变量"""
    # 先加载环境变量
    load_dotenv(Path(__file__).parent / ".env")
    
    missing_env = []
    warnings = []
    
    # 获取所有环境变量
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "").strip()
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
    CUSTOM_OCR_API_KEY = os.getenv("CUSTOM_OCR_API_KEY", "").strip()
    CUSTOM_OCR_BASE_URL = os.getenv("CUSTOM_OCR_BASE_URL", "").strip()
    
    # 检查必需的环境变量
    if not GEMINI_API_KEY:
        missing_env.append("GEMINI_API_KEY (文本纠错必需)")
    if not GEMINI_BASE_URL:
        missing_env.append("GEMINI_BASE_URL (文本纠错必需)")
    
    # 检查OCR服务 (至少需要一个)
    available_ocr_services = 0
    if DASHSCOPE_API_KEY:
        available_ocr_services += 1
    if MISTRAL_API_KEY:
        available_ocr_services += 1
    if CUSTOM_OCR_API_KEY and CUSTOM_OCR_BASE_URL:
        available_ocr_services += 1
    
    if available_ocr_services == 0:
        missing_env.append("至少一个OCR服务的API密钥 (DASHSCOPE_API_KEY, MISTRAL_API_KEY, 或 CUSTOM_OCR_API_KEY+CUSTOM_OCR_BASE_URL)")
    
    # 添加配置提醒
    if not DASHSCOPE_API_KEY:
        warnings.append("DashScope OCR服务未配置")
    if not MISTRAL_API_KEY:
        warnings.append("Mistral OCR服务未配置")
    if not (CUSTOM_OCR_API_KEY and CUSTOM_OCR_BASE_URL):
        warnings.append("自定义OCR服务未配置")
    
    return missing_env, warnings, {
        'dashscope': DASHSCOPE_API_KEY,
        'gemini_key': GEMINI_API_KEY,
        'gemini_url': GEMINI_BASE_URL,
        'mistral': MISTRAL_API_KEY,
        'custom_key': CUSTOM_OCR_API_KEY,
        'custom_url': CUSTOM_OCR_BASE_URL
    }

def auto_dependency_check():
    """自动检查依赖并给出解决方案"""
    print("🔍 正在检查系统依赖...")
    
    # 检查包依赖
    missing_deps = check_dependencies()
    if missing_deps:
        print("❌ 发现缺失的依赖包:")
        for dep in missing_deps:
            print(f"   • {dep}")
        print("\n💡 请运行以下命令安装缺失的依赖:")
        print("   uv sync")
        return False
    
    # 检查环境变量
    missing_env, warnings, env_vars = check_env_vars()
    if missing_env:
        print("❌ 发现缺失的环境变量:")
        for env in missing_env:
            print(f"   • {env}")
        print("\n💡 请在 .env 文件中设置以上环境变量")
        
        # 创建示例.env文件
        env_file = Path(__file__).parent / ".env"
        example_file = Path(__file__).parent / ".env.example"
        if not env_file.exists():
            if example_file.exists():
                print(f"📝 请复制 {example_file} 为 .env 并配置API密钥")
            else:
                sample_content = """# API配置
# Gemini纠错服务 (必需)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=your_gemini_base_url_here

# OCR服务 (至少配置一个)
DASHSCOPE_API_KEY=your_dashscope_api_key_here
MISTRAL_API_KEY=your_mistral_api_key_here
CUSTOM_OCR_API_KEY=your_custom_ocr_api_key_here
CUSTOM_OCR_BASE_URL=your_custom_ocr_base_url_here
"""
                env_file.write_text(sample_content)
                print(f"📝 已创建示例配置文件: {env_file}")
        
        return False
    
    # 显示警告信息
    if warnings:
        print("⚠️  配置提醒:")
        for warning in warnings:
            print(f"   • {warning}")
        print("   提示: 可以配置多个OCR服务以获得更多选择")
    
    print("✅ 所有依赖检查通过!")
    return True

# ---------- 2. Load env & basic checks ----------
# 自动检查依赖
if not auto_dependency_check():
    print("\n❌ 依赖检查失败，程序退出")
    sys.exit(1)

# 重新加载环境变量（已经在check_env_vars中加载过了）
load_dotenv(Path(__file__).parent / ".env")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "").strip()

# 添加更多OCR服务的环境变量
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1").strip()
CUSTOM_OCR_API_KEY = os.getenv("CUSTOM_OCR_API_KEY", "").strip()
CUSTOM_OCR_BASE_URL = os.getenv("CUSTOM_OCR_BASE_URL", "").strip()

# ---------- 3. OCR Service Architecture ----------
class OCRService(ABC):
    """OCR服务的抽象基类"""
    
    def __init__(self, name: str, api_key: str, base_url: str, model: str):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = None
        self.supports_streaming = False  # 默认不支持流式处理
        if api_key and base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查服务是否可用"""
        pass
    
    @abstractmethod
    def process_image(self, data_uri: str) -> Tuple[str, Dict]:
        """处理单张图像OCR
        
        返回: (OCR文本, usage统计)
        """
        pass
    
    def process_image_streaming(self, data_uri: str, progress_callback: Callable = None) -> Tuple[str, Dict]:
        """流式处理单张图像OCR（默认实现调用普通方法）
        
        参数:
            data_uri: 图像数据URI
            progress_callback: 进度回调函数
        
        返回: (OCR文本, usage统计)
        """
        return self.process_image(data_uri)
    
    def get_description(self) -> str:
        """获取服务描述"""
        streaming_indicator = " [流式]" if self.supports_streaming else ""
        return f"{self.name} ({self.model}){streaming_indicator}"


class DashScopeOCRService(OCRService):
    """阿里云DashScope OCR服务"""
    
    def __init__(self):
        super().__init__(
            name="阿里云DashScope",
            api_key=DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-vl-ocr-latest"
        )
        self.supports_streaming = True  # DashScope支持流式处理
    
    def is_available(self) -> bool:
        return bool(self.api_key and self.client)
    
    def process_image(self, data_uri: str) -> Tuple[str, Dict]:
        """非流式处理（为了向后兼容）"""
        return self.process_image_streaming(data_uri)
    
    def process_image_streaming(self, data_uri: str, progress_callback: Callable = None) -> Tuple[str, Dict]:
        """流式处理图像OCR"""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_uri,
                            "min_pixels": 28 * 28 * 4,
                            "max_pixels": 28 * 28 * 8192,
                        },
                    }
                ],
            }
        ]
        
        response_stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )
        
        ocr_text = ""
        usage_info = {}
        
        for chunk in response_stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunk_text = chunk.choices[0].delta.content
                ocr_text += chunk_text
                
                # 流式回调
                if progress_callback and chunk_text:
                    progress_callback('streaming_token', {
                        'service': 'DashScope',
                        'tokens': len(chunk_text.split()),
                        'chars': len(chunk_text)
                    })
            
            if hasattr(chunk, 'usage') and chunk.usage:
                usage_info = {
                    'input_tokens': getattr(chunk.usage, 'prompt_tokens', 0),
                    'output_tokens': getattr(chunk.usage, 'completion_tokens', 0),
                    'total_tokens': getattr(chunk.usage, 'total_tokens', 0)
                }
        
        return ocr_text, usage_info


class MistralOCRService(OCRService):
    """Mistral OCR服务"""
    
    def __init__(self):
        super().__init__(
            name="Mistral",
            api_key=MISTRAL_API_KEY,
            base_url=MISTRAL_BASE_URL,
            model="pixtral-12b-2409"
        )
        self.supports_streaming = True  # Mistral支持流式处理
    
    def is_available(self) -> bool:
        return bool(self.api_key and self.client)
    
    def process_image(self, data_uri: str) -> Tuple[str, Dict]:
        """非流式处理（为了向后兼容）"""
        return self.process_image_streaming(data_uri)
    
    def process_image_streaming(self, data_uri: str, progress_callback: Callable = None) -> Tuple[str, Dict]:
        """流式处理图像OCR"""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请识别这张图片中的所有文字内容，保持原始的排版和格式。只输出识别的文字，不要添加任何解释或说明。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_uri
                        }
                    }
                ]
            }
        ]
        
        try:
            # 尝试流式处理
            response_stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4000,
                temperature=0.1,
                stream=True
            )
            
            ocr_text = ""
            usage_info = {}
            
            for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_text = chunk.choices[0].delta.content
                    ocr_text += chunk_text
                    
                    # 流式回调
                    if progress_callback and chunk_text:
                        progress_callback('streaming_token', {
                            'service': 'Mistral',
                            'tokens': len(chunk_text.split()),
                            'chars': len(chunk_text)
                        })
                
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage_info = {
                        'input_tokens': getattr(chunk.usage, 'prompt_tokens', 0),
                        'output_tokens': getattr(chunk.usage, 'completion_tokens', 0),
                        'total_tokens': getattr(chunk.usage, 'total_tokens', 0)
                    }
            
            return ocr_text.strip(), usage_info
            
        except Exception as e:
            # 如果流式处理失败，回退到非流式处理
            if progress_callback:
                progress_callback('log', f"⚠️ Mistral流式处理失败，使用非流式处理: {e}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4000,
                temperature=0.1
            )
            
            ocr_text = response.choices[0].message.content.strip()
            
            # 提取usage信息
            usage_info = {}
            if hasattr(response, 'usage') and response.usage:
                usage_info = {
                    'input_tokens': getattr(response.usage, 'prompt_tokens', 0),
                    'output_tokens': getattr(response.usage, 'completion_tokens', 0),
                    'total_tokens': getattr(response.usage, 'total_tokens', 0)
                }
            
            return ocr_text, usage_info


class CustomOCRService(OCRService):
    """自定义OpenAI格式OCR服务"""
    
    def __init__(self, model_name: str = "gpt-4-vision-preview"):
        super().__init__(
            name="自定义OCR服务",
            api_key=CUSTOM_OCR_API_KEY,
            base_url=CUSTOM_OCR_BASE_URL,
            model=model_name
        )
    
    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url and self.client)
    
    def process_image(self, data_uri: str) -> Tuple[str, Dict]:
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请识别这张图片中的所有文字内容，保持原始的排版和格式。只输出识别的文字，不要添加任何解释或说明。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_uri
                        }
                    }
                ]
            }
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4000,
            temperature=0.1
        )
        
        ocr_text = response.choices[0].message.content.strip()
        
        # 提取usage信息
        usage_info = {}
        if hasattr(response, 'usage') and response.usage:
            usage_info = {
                'input_tokens': getattr(response.usage, 'prompt_tokens', 0),
                'output_tokens': getattr(response.usage, 'completion_tokens', 0),
                'total_tokens': getattr(response.usage, 'total_tokens', 0)
            }
        
        return ocr_text, usage_info


# ---------- 4. OCR Service Manager ----------
class OCRServiceManager:
    """OCR服务管理器"""
    
    def __init__(self):
        self.services = {
            "dashscope": DashScopeOCRService(),
            "mistral": MistralOCRService(),
            "custom": CustomOCRService()
        }
        
        # 检查可用服务
        self.available_services = {
            key: service for key, service in self.services.items()
            if service.is_available()
        }
    
    def get_available_services(self) -> Dict[str, OCRService]:
        """获取可用的OCR服务"""
        return self.available_services
    
    def get_service(self, service_key: str) -> OCRService:
        """获取指定的OCR服务"""
        if service_key not in self.available_services:
            raise ValueError(f"OCR服务 '{service_key}' 不可用")
        return self.available_services[service_key]


# 初始化OCR服务管理器
ocr_manager = OCRServiceManager()

# ---------- 5. Initialize Gemini client ----------
gemini_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL,
)

# ---------- 6. Interactive functions ----------
def select_ocr_service() -> str:
    """交互式选择OCR服务"""
    available_services = ocr_manager.get_available_services()
    
    if not available_services:
        print("❌ 没有可用的OCR服务，请检查环境变量配置")
        return None
    
    print("\n🔧 选择OCR服务：")
    service_keys = list(available_services.keys())
    
    for i, (key, service) in enumerate(available_services.items(), 1):
        print(f"  {i}. {service.get_description()}")
    
    while True:
        try:
            choice = input(f"\n请选择OCR服务 (1-{len(service_keys)}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(service_keys):
                selected_key = service_keys[choice_num - 1]
                selected_service = available_services[selected_key]
                print(f"✅ 已选择: {selected_service.get_description()}")
                return selected_key
            else:
                print("❌ 无效选择，请重新输入")
        except ValueError:
            print("❌ 请输入有效数字")


def get_terminology_files() -> List[Path]:
    """获取terminology文件夹中的所有专有名词文件"""
    terminology_dir = Path("terminology")
    if not terminology_dir.exists():
        terminology_dir.mkdir()
        print("📁 已创建 terminology 文件夹")
        return []
    
    txt_files = list(terminology_dir.glob("*.txt"))
    return txt_files


def select_terminology_file(terminology_files: List[Path]) -> Path | None:
    """交互式选择专有名词文件"""
    if not terminology_files:
        print("📝 terminology 文件夹中没有找到专有名词文件，将跳过专有名词纠错功能")
        return None
    
    print("\n📝 找到以下专有名词文件：")
    for i, file in enumerate(terminology_files, 1):
        print(f"  {i}. {file.name}")
    
    print(f"  {len(terminology_files) + 1}. 不使用专有名词文件")
    
    while True:
        try:
            choice = input(f"\n请选择专有名词文件 (1-{len(terminology_files) + 1}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(terminology_files):
                return terminology_files[choice_num - 1]
            elif choice_num == len(terminology_files) + 1:
                return None
            else:
                print("❌ 无效选择，请重新输入")
        except ValueError:
            print("❌ 请输入有效数字")


def load_terminology(terminology_file: Path | None) -> str:
    """加载专有名词文件内容"""
    if not terminology_file or not terminology_file.exists():
        return ""
    
    try:
        content = terminology_file.read_text(encoding="utf-8").strip()
        terms = [line.strip() for line in content.split('\n') if line.strip()]
        return "、".join(terms) if terms else ""
    except Exception as e:
        print(f"⚠️  读取专有名词文件失败: {e}")
        return ""


def select_preprocessing_mode():
    """交互式选择图像预处理模式"""
    from image_preprocessor import PreprocessingMode, create_preprocessor_config
    
    print("\n🎨 选择图像预处理模式：")
    modes = [
        (PreprocessingMode.NONE, "不处理", "保持原始图像，适合高质量扫描件"),
        (PreprocessingMode.BASIC, "基础处理", "轻量级降噪和锐化，适合一般文档"),
        (PreprocessingMode.DOCUMENT, "文档优化", "专为扫描文档优化，包含倾斜矫正和二值化"),
        (PreprocessingMode.PHOTO, "照片优化", "适合手机拍照的文档，包含透视矫正"),
        (PreprocessingMode.AGGRESSIVE, "激进处理", "最大化OCR效果，适合低质量图像")
    ]
    
    for i, (mode, name, desc) in enumerate(modes, 1):
        print(f"  {i}. {name} - {desc}")
    
    while True:
        try:
            choice = input(f"\n请选择预处理模式 (1-{len(modes)}，默认为3): ").strip()
            
            if not choice:  # 默认选择文档优化
                choice_num = 3
            else:
                choice_num = int(choice)
            
            if 1 <= choice_num <= len(modes):
                selected_mode = modes[choice_num - 1][0]
                selected_name = modes[choice_num - 1][1]
                print(f"✅ 已选择预处理模式: {selected_name}")
                
                # 创建配置
                config = create_preprocessor_config(mode=selected_mode.value)
                return config
            else:
                print("❌ 无效选择，请重新输入")
        except ValueError:
            print("❌ 请输入有效数字")


def get_pdf_files() -> List[Path]:
    """获取input文件夹中的所有PDF文件"""
    input_dir = Path("input")
    if not input_dir.exists():
        input_dir.mkdir()
        print("📁 已创建 input 文件夹，请将PDF文件放入其中")
        return []
    
    pdf_files = list(input_dir.glob("*.pdf"))
    return pdf_files


def select_pdf_file(pdf_files: List[Path]) -> List[Path]:
    """交互式选择PDF文件"""
    if not pdf_files:
        print("❌ input 文件夹中没有找到PDF文件")
        return []
    
    print("\n📋 找到以下PDF文件：")
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"  {i}. {pdf_file.name}")
    
    print(f"  {len(pdf_files) + 1}. 全部文件")
    
    while True:
        try:
            choice = input(f"\n请选择要处理的文件 (1-{len(pdf_files) + 1}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(pdf_files):
                return [pdf_files[choice_num - 1]]
            elif choice_num == len(pdf_files) + 1:
                return pdf_files
            else:
                print("❌ 无效选择，请重新输入")
        except ValueError:
            print("❌ 请输入有效数字")


def get_pdf_page_count(pdf_path: Path) -> int:
    """获取PDF文件的页数"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = pypdf.PdfReader(file)
            return len(reader.pages)
    except Exception as e:
        print(f"❌ 无法读取PDF文件 {pdf_path}: {e}")
        return 0


def select_page_range(pdf_path: Path) -> Tuple[int, int]:
    """交互式选择页数范围"""
    total_pages = get_pdf_page_count(pdf_path)
    
    if total_pages == 0:
        return 1, 1
    
    print(f"\n📄 PDF文件 '{pdf_path.name}' 共有 {total_pages} 页")
    
    while True:
        try:
            start_input = input(f"请输入起始页码 (1-{total_pages}，默认为1): ").strip()
            start_page = int(start_input) if start_input else 1
            
            if not (1 <= start_page <= total_pages):
                print(f"❌ 起始页码必须在 1-{total_pages} 之间")
                continue
            
            end_input = input(f"请输入结束页码 ({start_page}-{total_pages}，默认为{start_page}): ").strip()
            end_page = int(end_input) if end_input else start_page
            
            if not (start_page <= end_page <= total_pages):
                print(f"❌ 结束页码必须在 {start_page}-{total_pages} 之间")
                continue
            
            return start_page, end_page
            
        except ValueError:
            print("❌ 请输入有效数字")


# ---------- 5. Helpers ----------
def pil_to_data_uri(img) -> str:
    """PIL Image -> data URI accepted by DashScope vision endpoint."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def get_images_for_page(pdf: str, page_zero_idx: int, enable_preprocessing: bool = True, preprocessing_config = None):
    """Convert one PDF page (0‑based) to a list of PIL images with optional preprocessing."""
    try:
        # 转换PDF页面为图像
        images = convert_from_path(
            pdf,
            dpi=300,
            first_page=page_zero_idx + 1,
            last_page=page_zero_idx + 1,
        )
        
        # 如果启用了预处理，对每张图像进行预处理
        if enable_preprocessing and images:
            from image_preprocessor import ImagePreprocessor, PreprocessingConfig
            
            # 使用默认配置或传入的配置
            if preprocessing_config is None:
                from image_preprocessor import create_preprocessor_config
                preprocessing_config = create_preprocessor_config(mode="document")
            
            preprocessor = ImagePreprocessor(preprocessing_config)
            
            processed_images = []
            for img in images:
                processed_img, stats = preprocessor.preprocess_image(img, preprocessing_config)
                processed_images.append(processed_img)
                
                # 可选：打印预处理统计信息
                if stats.get("operations_applied"):
                    print(f"  📈 图像预处理: {', '.join(stats['operations_applied'])}")
                    if stats.get("quality_score"):
                        print(f"  🎯 质量评分: {stats['quality_score']:.1f}/100")
            
            return processed_images
        
        return images
        
    except pdf_exc.PDFInfoNotInstalledError as e:
        raise RuntimeError(
            "pdf2image 需要依赖 poppler，请先安装。"
            "macOS: brew install poppler,  Linux: sudo apt install poppler-utils"
        ) from e


def correct_text_with_gemini(ocr_text: str, terminology_terms: str = "") -> tuple[str, dict]:
    """使用第三方Gemini服务纠错OCR文本并格式化为markdown
    
    返回: (纠错后的文本, token使用统计)
    """
    try:
        terminology_instruction = ""
        if terminology_terms:
            terminology_instruction = f"\n\n**专有名词参考**：{terminology_terms}\n请根据上述专有名词列表纠正文本中出现的相关词汇。"
        
        prompt = f"""请对以下OCR识别的文本进行专业的处理和Markdown格式化：

## 处理要求

### 1. 文本纠错
- 修正OCR识别错误、错别字和格式问题
- 修复逻辑不通顺的地方，保持原文意思
- 补充缺失的标点符号和段落结构

### 2. 智能结构识别
- 自动识别文档的层级结构（标题、章节、段落等）
- 识别列表、表格、引用等特殊内容
- 保持原文的逻辑顺序和信息完整性

### 3. 专业Markdown格式化
- **标题层级**：使用 # ## ### #### 标记不同级别标题
- **段落结构**：合理分段，保持良好的可读性
- **列表格式**：使用 - 或 1. 格式化列表项
- **强调内容**：使用 **粗体** 和 *斜体* 突出重点
- **引用格式**：使用 > 标记引用内容
- **代码格式**：使用 ` 或 ``` 标记代码片段
- **表格格式**：识别并格式化表格内容

{terminology_instruction}

## 输出要求
- **直接输出**：只输出处理后的Markdown文档，不要添加任何说明
- **语法规范**：确保符合标准Markdown语法
- **结构清晰**：层次分明，便于阅读和编辑
- **内容完整**：保持原文的所有重要信息

---

**待处理文本**：
{ocr_text}"""
        
        response = gemini_client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            stream=False,
        )
        
        # 提取token使用统计
        usage_stats = {}
        if hasattr(response, 'usage') and response.usage:
            usage_stats = {
                'input_tokens': getattr(response.usage, 'prompt_tokens', 0),
                'output_tokens': getattr(response.usage, 'completion_tokens', 0),
                'total_tokens': getattr(response.usage, 'total_tokens', 0)
            }
        
        return response.choices[0].message.content.strip(), usage_stats
    except Exception as e:
        print(f"⚠️  Gemini纠错失败: {e}")
        return ocr_text, {}


def process_single_file(pdf_path: Path, start_page: int, end_page: int, terminology_terms: str = "", ocr_service_key: str = "dashscope", preprocessing_config = None) -> str:
    """处理单个PDF文件的OCR和纠错"""
    
    # 获取选择的OCR服务
    ocr_service = ocr_manager.get_service(ocr_service_key)
    
    print(f"\n🔄 开始处理文件: {pdf_path.name}")
    print(f"📄 页数范围: {start_page}-{end_page}")
    print(f"🔧 OCR服务: {ocr_service.get_description()}")
    
    # 显示预处理配置
    if preprocessing_config:
        print(f"🎨 图像预处理: {preprocessing_config.mode.value} 模式")
    else:
        print("🎨 图像预处理: 已禁用")
    
    # 创建输出目录
    out_dir = Path("ocr_output")
    out_dir.mkdir(exist_ok=True)
    
    all_pages_text = []
    pages = list(range(start_page - 1, end_page))  # 转换为0-based索引
    total_pages = len(pages)
    
    # Token消耗统计 - 分别统计OCR和纠错的消耗
    ocr_input_tokens = 0
    ocr_output_tokens = 0
    ocr_total_tokens = 0
    
    gemini_input_tokens = 0
    gemini_output_tokens = 0
    gemini_total_tokens = 0
    
    total_tokens = 0
    
    # 创建进度条
    progress_bar = tqdm(total=total_pages, desc=f"处理 {pdf_path.name}")
    
    for i, page_idx in enumerate(pages):
        try:
            # 更新进度条描述，显示当前页数和token消耗
            progress_bar.set_description(
                f"处理 {pdf_path.name} "
                f"[{i+1}/{total_pages}页] "
                f"[Token: {total_tokens:,}]"
            )
            
            # OCR处理（带预处理）
            enable_preprocessing = preprocessing_config is not None
            imgs = get_images_for_page(str(pdf_path), page_idx, enable_preprocessing, preprocessing_config)
            if not imgs:
                tqdm.write(f"⚠️  第 {page_idx + 1} 页转换图像失败，已跳过")
                progress_bar.update(1)
                continue

            data_uri = pil_to_data_uri(imgs[0])

            # 使用选择的OCR服务处理图像
            tqdm.write(f"🔍 使用 {ocr_service.get_description()} 识别第 {page_idx + 1} 页...")
            ocr_text, ocr_usage = ocr_service.process_image(data_uri)

            # 更新OCR token统计
            if ocr_usage:
                input_tokens = ocr_usage.get('input_tokens', 0)
                output_tokens = ocr_usage.get('output_tokens', 0)
                page_total_tokens = ocr_usage.get('total_tokens', input_tokens + output_tokens)
                
                ocr_input_tokens += input_tokens
                ocr_output_tokens += output_tokens
                ocr_total_tokens += page_total_tokens
                total_tokens += page_total_tokens
                
                tqdm.write(f"📊 第 {page_idx + 1} 页 OCR Token消耗: {page_total_tokens:,} (输入: {input_tokens:,}, 输出: {output_tokens:,})")

            # Gemini纠错
            tqdm.write(f"🔧 使用Gemini纠错第 {page_idx + 1} 页...")
            corrected_text, gemini_usage = correct_text_with_gemini(ocr_text, terminology_terms)
            
            # 更新Gemini token统计
            if gemini_usage:
                gemini_page_input = gemini_usage.get('input_tokens', 0)
                gemini_page_output = gemini_usage.get('output_tokens', 0)
                gemini_page_total = gemini_usage.get('total_tokens', gemini_page_input + gemini_page_output)
                
                gemini_input_tokens += gemini_page_input
                gemini_output_tokens += gemini_page_output
                gemini_total_tokens += gemini_page_total
                total_tokens += gemini_page_total
                
                tqdm.write(f"📊 第 {page_idx + 1} 页 Gemini Token消耗: {gemini_page_total:,} (输入: {gemini_page_input:,}, 输出: {gemini_page_output:,})")
            
            # 保存单页结果
            page_file = out_dir / f"{pdf_path.stem}_page_{page_idx + 1}.md"
            page_file.write_text(corrected_text, encoding="utf-8")
            
            all_pages_text.append(corrected_text)
            
            # 更新进度条
            progress_bar.update(1)
            progress_bar.set_description(
                f"处理 {pdf_path.name} "
                f"[{i+1}/{total_pages}页] "
                f"[Token: {total_tokens:,}]"
            )
            
            tqdm.write(f"✓ 第 {page_idx + 1} 页处理完成")
            
        except Exception as e:
            tqdm.write(f"❌ 第 {page_idx + 1} 页处理失败: {e}")
            progress_bar.update(1)
            continue
    
    # 关闭进度条
    progress_bar.close()
    
    # 拼接所有页面
    combined_text = "\n\n".join(all_pages_text)
    combined_file = out_dir / f"{pdf_path.stem}_combined.md"
    combined_file.write_text(combined_text, encoding="utf-8")
    
    print(f"✅ 文件 {pdf_path.name} 处理完成")
    print(f"📁 合并文件保存至: {combined_file}")
    print(f"💰 Token消耗统计:")
    print(f"   OCR ({ocr_service.name}): {ocr_total_tokens:,} tokens (输入: {ocr_input_tokens:,}, 输出: {ocr_output_tokens:,})")
    print(f"   纠错 (Gemini): {gemini_total_tokens:,} tokens (输入: {gemini_input_tokens:,}, 输出: {gemini_output_tokens:,})")
    print(f"   总计: {total_tokens:,} tokens")
    
    return combined_text


def process_single_file_with_progress_callback(pdf_path: Path, start_page: int, end_page: int, terminology_terms: str = "", ocr_service_key: str = "dashscope", progress_callback: Callable = None, preprocessing_config = None):
    """
    带进度回调的单文件处理函数
    
    参数:
        pdf_path: PDF文件路径
        start_page: 起始页 (1-based)
        end_page: 结束页 (1-based)
        terminology_terms: 专有名词列表
        ocr_service_key: OCR服务键名
        progress_callback: 进度回调函数，接收(msg_type, data, **kwargs)
    
    返回: 合并后的文本内容
    """
    # 获取OCR服务
    ocr_service = ocr_manager.get_service(ocr_service_key)
    if not ocr_service:
        raise ValueError(f"OCR服务 '{ocr_service_key}' 不可用")
    
    # 输出目录
    out_dir = Path("ocr_output")
    out_dir.mkdir(exist_ok=True)
    
    all_pages_text = []
    pages = list(range(start_page - 1, end_page))  # 转换为0-based索引
    total_pages = len(pages)
    
    # Token消耗统计 - 分别统计OCR和纠错的消耗
    ocr_input_tokens = 0
    ocr_output_tokens = 0
    ocr_total_tokens = 0
    
    gemini_input_tokens = 0
    gemini_output_tokens = 0
    gemini_total_tokens = 0
    
    total_tokens = 0
    
    if progress_callback:
        progress_callback('log', f"开始处理文件: {pdf_path.name}")
        progress_callback('log', f"页面范围: {start_page}-{end_page} (共{total_pages}页)")
        progress_callback('log', f"OCR服务: {ocr_service.get_description()}")
    
    for i, page_idx in enumerate(pages):
        try:
            # 通知页面开始处理
            if progress_callback:
                progress_callback('page_start', (page_idx, total_pages))
                progress_callback('log', f"🔍 处理第 {page_idx + 1} 页...")
            
            # OCR处理（带预处理）
            enable_preprocessing = preprocessing_config is not None
            imgs = get_images_for_page(str(pdf_path), page_idx, enable_preprocessing, preprocessing_config)
            if not imgs:
                if progress_callback:
                    progress_callback('log', f"⚠️  第 {page_idx + 1} 页转换图像失败，已跳过", tag="error")
                continue

            data_uri = pil_to_data_uri(imgs[0])

            # 使用选择的OCR服务处理图像 - 使用流式处理
            if progress_callback:
                progress_callback('log', f"🔍 使用 {ocr_service.get_description()} 识别第 {page_idx + 1} 页...")
            
            # 检查是否支持流式处理
            if hasattr(ocr_service, 'process_image_streaming') and ocr_service.supports_streaming:
                ocr_text, ocr_usage = ocr_service.process_image_streaming(data_uri, progress_callback)
            else:
                ocr_text, ocr_usage = ocr_service.process_image(data_uri)

            # 更新OCR token统计
            if ocr_usage:
                input_tokens = ocr_usage.get('input_tokens', 0)
                output_tokens = ocr_usage.get('output_tokens', 0)
                page_total_tokens = ocr_usage.get('total_tokens', input_tokens + output_tokens)
                
                ocr_input_tokens += input_tokens
                ocr_output_tokens += output_tokens
                ocr_total_tokens += page_total_tokens
                total_tokens += page_total_tokens
                
                if progress_callback:
                    progress_callback('ocr_token', ocr_usage)

            # Gemini纠错
            if progress_callback:
                progress_callback('log', f"🔧 使用Gemini纠错第 {page_idx + 1} 页...")
            
            corrected_text, gemini_usage = correct_text_with_gemini_streaming(ocr_text, terminology_terms, progress_callback)
            
            # 更新Gemini token统计
            if gemini_usage:
                gemini_page_input = gemini_usage.get('input_tokens', 0)
                gemini_page_output = gemini_usage.get('output_tokens', 0)
                gemini_page_total = gemini_usage.get('total_tokens', gemini_page_input + gemini_page_output)
                
                gemini_input_tokens += gemini_page_input
                gemini_output_tokens += gemini_page_output
                gemini_total_tokens += gemini_page_total
                total_tokens += gemini_page_total
                
                if progress_callback:
                    progress_callback('gemini_token', gemini_usage)
            
            # 保存单页结果
            page_file = out_dir / f"{pdf_path.stem}_page_{page_idx + 1}.md"
            page_file.write_text(corrected_text, encoding="utf-8")
            
            all_pages_text.append(corrected_text)
            
            # 通知页面处理完成
            if progress_callback:
                progress_callback('page_complete', page_idx)
            
        except Exception as e:
            if progress_callback:
                progress_callback('log', f"❌ 第 {page_idx + 1} 页处理失败: {e}", tag="error")
            continue
    
    # 拼接所有页面
    combined_text = "\n\n".join(all_pages_text)
    combined_file = out_dir / f"{pdf_path.stem}_combined.md"
    combined_file.write_text(combined_text, encoding="utf-8")
    
    if progress_callback:
        progress_callback('log', f"✅ 文件 {pdf_path.name} 处理完成", tag="success")
        progress_callback('log', f"📁 合并文件保存至: {combined_file}")
        progress_callback('log', f"💰 总Token消耗: {total_tokens:,}", tag="token")
    
    return combined_text


def correct_text_with_gemini_streaming(text: str, terminology_terms: str = "", progress_callback: Callable = None):
    """
    使用Gemini进行文本纠错和优化 - 智能选择可用服务
    
    参数:
        text: 需要纠错的文本
        terminology_terms: 专有名词列表，用于提高纠错准确性
        progress_callback: 进度回调函数
    
    返回: (纠错后的文本, token使用统计)
    """
    # 检查环境变量
    if not GEMINI_API_KEY or not GEMINI_BASE_URL:
        if progress_callback:
            progress_callback('log', "⚠️ Gemini配置不完整，跳过纠错", tag="warning")
        return text, {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
    
    # 优先尝试第三方服务（更稳定）
    try:
        return correct_text_with_gemini(text, terminology_terms)
    except Exception as third_party_error:
        if progress_callback:
            progress_callback('log', f"⚠️ 第三方Gemini服务失败，尝试官方服务: {third_party_error}", tag="warning")
        
        # 回退到官方服务
        try:
            import google.generativeai as genai
            
            # 配置Gemini客户端
            genai.configure(api_key=GEMINI_API_KEY, transport='rest')
            
            # 配置生成参数
            generation_config = {
                "temperature": 0.1,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
            
            # 创建模型
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                generation_config=generation_config,
            )
            
            # 构建提示词
            terminology_prompt = f"\n\n专有名词参考（请确保这些词汇在纠错时保持正确）：\n{terminology_terms}" if terminology_terms.strip() else ""
            
            prompt = f"""请对以下OCR识别的文本进行专业的处理和Markdown格式化：

## 处理要求

### 1. 文本纠错
- 修正OCR识别错误、错别字和格式问题
- 修复逻辑不通顺的地方，保持原文意思
- 补充缺失的标点符号和段落结构

### 2. 智能结构识别
- 自动识别文档的层级结构（标题、章节、段落等）
- 识别列表、表格、引用等特殊内容
- 保持原文的逻辑顺序和信息完整性

### 3. 专业Markdown格式化
- **标题层级**：使用 # ## ### #### 标记不同级别标题
- **段落结构**：合理分段，保持良好的可读性
- **列表格式**：使用 - 或 1. 格式化列表项
- **强调内容**：使用 **粗体** 和 *斜体* 突出重点
- **引用格式**：使用 > 标记引用内容
- **代码格式**：使用 ` 或 ``` 标记代码片段
- **表格格式**：识别并格式化表格内容

{terminology_prompt}

## 输出要求
- **直接输出**：只输出处理后的Markdown文档，不要添加任何说明
- **语法规范**：确保符合标准Markdown语法
- **结构清晰**：层次分明，便于阅读和编辑
- **内容完整**：保持原文的所有重要信息

---

**待处理文本**：
{text}"""

            if progress_callback:
                progress_callback('log', "🤖 开始Gemini纠错...")
            
            # 使用非流式生成
            response = model.generate_content(prompt, stream=False)
            
            # 直接获取生成的文本
            corrected_text = response.text
            total_chars = len(corrected_text)
            
            # 获取usage统计
            try:
                usage_metadata = response.usage_metadata
                token_usage = {
                    'input_tokens': getattr(usage_metadata, 'prompt_token_count', 0),
                    'output_tokens': getattr(usage_metadata, 'candidates_token_count', 0),
                    'total_tokens': getattr(usage_metadata, 'total_token_count', 0)
                }
            except:
                # 如果无法获取usage，使用估算值
                estimated_input = len(prompt.split())
                estimated_output = len(corrected_text.split())
                token_usage = {
                    'input_tokens': estimated_input,
                    'output_tokens': estimated_output,
                    'total_tokens': estimated_input + estimated_output
                }
            
            if progress_callback:
                progress_callback('log', f"✅ 官方Gemini纠错完成，生成 {total_chars} 个字符")
            
            return corrected_text, token_usage
            
        except Exception as official_error:
            if progress_callback:
                progress_callback('log', f"⚠️ 官方Gemini服务也失败，使用原文: {official_error}", tag="error")
            
            # 所有服务都失败，返回原文
            return text, {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}


# ---------- 6. Main program ----------
def main():
    """主程序"""
    print("🔥 欢迎使用增强版OCR程序")
    print("✨ 功能: 多OCR服务支持 + 图像预处理 + Gemini纠错 + 结构识别 + Markdown输出")
    
    # 选择OCR服务
    selected_ocr_service = select_ocr_service()
    if not selected_ocr_service:
        return
    
    # 选择图像预处理模式
    preprocessing_config = select_preprocessing_mode()
    
    # 获取并选择专有名词文件
    terminology_files = get_terminology_files()
    selected_terminology_file = select_terminology_file(terminology_files)
    terminology_terms = load_terminology(selected_terminology_file)
    
    if terminology_terms:
        print(f"✅ 已加载专有名词文件: {selected_terminology_file.name}")
    else:
        print("📝 未使用专有名词文件")
    
    # 获取PDF文件列表
    pdf_files = get_pdf_files()
    if not pdf_files:
        return
    
    # 选择要处理的文件
    selected_files = select_pdf_file(pdf_files)
    if not selected_files:
        return
    
    # 处理每个选中的文件
    for pdf_path in selected_files:
        # 选择页数范围
        start_page, end_page = select_page_range(pdf_path)
        
        # 处理文件
        try:
            process_single_file(pdf_path, start_page, end_page, terminology_terms, selected_ocr_service, preprocessing_config)
        except Exception as e:
            print(f"❌ 处理文件 {pdf_path.name} 时发生错误: {e}")
            continue
    
    print("\n🎉 全部处理完成！")
    print("📁 结果保存在 ocr_output/ 目录中")
    print("   - 单页文件: {文件名}_page_{页码}.md (Markdown格式)")
    print("   - 合并文件: {文件名}_combined.md (Markdown格式)")


if __name__ == "__main__":
    main()
