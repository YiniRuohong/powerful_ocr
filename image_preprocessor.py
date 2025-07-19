#!/usr/bin/env python3
"""
图像预处理模块 - 提供OCR前的图像质量优化功能
包含去噪、锐化、对比度调整、倾斜矫正等功能
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import math


class PreprocessingMode(Enum):
    """预处理模式"""
    NONE = "none"              # 不处理
    BASIC = "basic"            # 基础处理（去噪+锐化）
    DOCUMENT = "document"      # 文档优化（适合扫描文档）
    PHOTO = "photo"           # 照片优化（适合手机拍照）
    AGGRESSIVE = "aggressive"  # 激进处理（最大化OCR效果）


@dataclass
class PreprocessingConfig:
    """预处理配置"""
    mode: PreprocessingMode = PreprocessingMode.DOCUMENT
    
    # 基础设置
    enable_noise_reduction: bool = True
    enable_sharpening: bool = True
    enable_contrast_enhancement: bool = True
    enable_deskewing: bool = True
    enable_perspective_correction: bool = True
    
    # 高级设置
    noise_reduction_strength: float = 1.0  # 0.0-2.0
    sharpening_strength: float = 1.0       # 0.0-3.0
    contrast_factor: float = 1.2           # 0.5-2.0
    brightness_factor: float = 1.0         # 0.5-2.0
    
    # 几何校正设置
    deskewing_threshold: float = 0.5       # 度数阈值
    perspective_detection_threshold: float = 0.02
    
    # 输出设置
    output_dpi: int = 300                  # 输出DPI
    binarization: bool = False             # 是否二值化
    grayscale: bool = False               # 是否转灰度


class ImagePreprocessor:
    """图像预处理器"""
    
    def __init__(self, config: PreprocessingConfig = None):
        self.config = config or PreprocessingConfig()
        
    def preprocess_image(self, image: Image.Image, config: PreprocessingConfig = None) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        预处理图像
        
        参数:
            image: PIL图像对象
            config: 预处理配置（可选，覆盖默认配置）
        
        返回:
            (处理后的图像, 处理统计信息)
        """
        if config:
            self.config = config
            
        stats = {
            "original_size": image.size,
            "operations_applied": [],
            "processing_time": 0,
            "quality_score": 0.0
        }
        
        import time
        start_time = time.time()
        
        # 转换为OpenCV格式进行处理
        cv_image = self._pil_to_cv2(image)
        
        # 根据模式应用预设配置
        self._apply_mode_preset()
        
        # 1. 几何校正
        if self.config.enable_deskewing or self.config.enable_perspective_correction:
            cv_image, correction_stats = self._correct_geometry(cv_image)
            stats["operations_applied"].extend(correction_stats)
        
        # 2. 降噪
        if self.config.enable_noise_reduction:
            cv_image = self._reduce_noise(cv_image)
            stats["operations_applied"].append("noise_reduction")
        
        # 3. 对比度和亮度调整
        if self.config.enable_contrast_enhancement:
            cv_image = self._enhance_contrast(cv_image)
            stats["operations_applied"].append("contrast_enhancement")
        
        # 4. 锐化
        if self.config.enable_sharpening:
            cv_image = self._sharpen_image(cv_image)
            stats["operations_applied"].append("sharpening")
        
        # 5. 二值化（如果启用）
        if self.config.binarization:
            cv_image = self._binarize_image(cv_image)
            stats["operations_applied"].append("binarization")
        
        # 6. 灰度转换（如果启用）
        if self.config.grayscale and len(cv_image.shape) == 3:
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            stats["operations_applied"].append("grayscale_conversion")
        
        # 转换回PIL格式
        processed_image = self._cv2_to_pil(cv_image)
        
        # DPI调整
        if self.config.output_dpi != 300:
            processed_image = self._adjust_dpi(processed_image)
            stats["operations_applied"].append("dpi_adjustment")
        
        # 计算处理时间和质量评分
        stats["processing_time"] = time.time() - start_time
        stats["processed_size"] = processed_image.size
        stats["quality_score"] = self._calculate_quality_score(cv_image)
        
        return processed_image, stats
    
    def _apply_mode_preset(self):
        """根据预处理模式应用预设配置"""
        if self.config.mode == PreprocessingMode.NONE:
            # 禁用所有处理
            self.config.enable_noise_reduction = False
            self.config.enable_sharpening = False
            self.config.enable_contrast_enhancement = False
            self.config.enable_deskewing = False
            self.config.enable_perspective_correction = False
            
        elif self.config.mode == PreprocessingMode.BASIC:
            # 轻量级处理
            self.config.noise_reduction_strength = 0.8
            self.config.sharpening_strength = 0.8
            self.config.contrast_factor = 1.1
            self.config.enable_deskewing = False
            self.config.enable_perspective_correction = False
            
        elif self.config.mode == PreprocessingMode.DOCUMENT:
            # 文档扫描优化
            self.config.noise_reduction_strength = 1.0
            self.config.sharpening_strength = 1.2
            self.config.contrast_factor = 1.3
            self.config.brightness_factor = 1.05
            self.config.enable_deskewing = True
            self.config.binarization = True
            
        elif self.config.mode == PreprocessingMode.PHOTO:
            # 手机拍照优化
            self.config.noise_reduction_strength = 1.2
            self.config.sharpening_strength = 1.0
            self.config.contrast_factor = 1.2
            self.config.enable_perspective_correction = True
            self.config.enable_deskewing = True
            
        elif self.config.mode == PreprocessingMode.AGGRESSIVE:
            # 激进处理
            self.config.noise_reduction_strength = 1.5
            self.config.sharpening_strength = 2.0
            self.config.contrast_factor = 1.5
            self.config.brightness_factor = 1.1
            self.config.enable_deskewing = True
            self.config.enable_perspective_correction = True
            self.config.binarization = True
    
    def _pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """PIL图像转OpenCV格式"""
        if pil_image.mode == 'RGB':
            return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        elif pil_image.mode == 'RGBA':
            return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)
        elif pil_image.mode == 'L':
            return np.array(pil_image)
        else:
            return cv2.cvtColor(np.array(pil_image.convert('RGB')), cv2.COLOR_RGB2BGR)
    
    def _cv2_to_pil(self, cv_image: np.ndarray) -> Image.Image:
        """OpenCV图像转PIL格式"""
        if len(cv_image.shape) == 3:
            return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
        else:
            return Image.fromarray(cv_image)
    
    def _correct_geometry(self, image: np.ndarray) -> Tuple[np.ndarray, list]:
        """几何校正：包括倾斜矫正和透视矫正"""
        corrections_applied = []
        
        try:
            # 1. 倾斜矫正
            if self.config.enable_deskewing:
                angle = self._detect_skew_angle(image)
                if abs(angle) > self.config.deskewing_threshold:
                    image = self._rotate_image(image, angle)
                    corrections_applied.append(f"deskewing_{angle:.1f}deg")
            
            # 2. 透视矫正
            if self.config.enable_perspective_correction:
                corrected_image = self._correct_perspective(image)
                if corrected_image is not None:
                    image = corrected_image
                    corrections_applied.append("perspective_correction")
                    
        except Exception as e:
            print(f"⚠️ 几何校正警告: {e}")
        
        return image, corrections_applied
    
    def _detect_skew_angle(self, image: np.ndarray) -> float:
        """检测文档倾斜角度"""
        try:
            # 转为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 边缘检测
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # 霍夫直线检测
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None:
                angles = []
                for rho, theta in lines[:20]:  # 只考虑前20条直线
                    angle = np.degrees(theta) - 90
                    if -45 < angle < 45:  # 只考虑合理的倾斜角度
                        angles.append(angle)
                
                if angles:
                    # 返回角度的中位数
                    return np.median(angles)
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """旋转图像"""
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        
        # 计算旋转矩阵
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # 计算新的边界框
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        # 调整旋转矩阵
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        
        # 执行旋转
        rotated = cv2.warpAffine(image, M, (new_w, new_h), 
                                flags=cv2.INTER_CUBIC, 
                                borderMode=cv2.BORDER_REPLICATE)
        
        return rotated
    
    def _correct_perspective(self, image: np.ndarray) -> Optional[np.ndarray]:
        """透视矫正"""
        try:
            # 转为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 高斯模糊
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # 边缘检测
            edged = cv2.Canny(blurred, 75, 200)
            
            # 寻找轮廓
            contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return None
            
            # 按面积排序，取最大的轮廓
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            
            for contour in contours[:5]:  # 检查前5个最大轮廓
                # 轮廓近似
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # 如果找到4个顶点的近似矩形
                if len(approx) == 4:
                    # 检查面积是否足够大（至少是图像面积的10%）
                    contour_area = cv2.contourArea(approx)
                    image_area = image.shape[0] * image.shape[1]
                    
                    if contour_area > image_area * 0.1:
                        return self._apply_perspective_transform(image, approx)
            
            return None
            
        except Exception:
            return None
    
    def _apply_perspective_transform(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """应用透视变换"""
        # 重新排列角点：左上、右上、右下、左下
        corners = corners.reshape(4, 2)
        
        # 计算重心
        center = np.mean(corners, axis=0)
        
        # 按角度排序
        angles = np.arctan2(corners[:, 1] - center[1], corners[:, 0] - center[0])
        corners = corners[np.argsort(angles)]
        
        # 确保正确的顶点顺序
        rect = np.zeros((4, 2), dtype=np.float32)
        
        # 左上角：x+y最小
        s = corners.sum(axis=1)
        rect[0] = corners[np.argmin(s)]
        
        # 右下角：x+y最大
        rect[2] = corners[np.argmax(s)]
        
        # 右上角：y-x最小
        diff = np.diff(corners, axis=1)
        rect[1] = corners[np.argmin(diff)]
        
        # 左下角：y-x最大
        rect[3] = corners[np.argmax(diff)]
        
        # 计算目标矩形的宽度和高度
        width_a = np.linalg.norm(rect[2] - rect[3])
        width_b = np.linalg.norm(rect[1] - rect[0])
        max_width = max(int(width_a), int(width_b))
        
        height_a = np.linalg.norm(rect[1] - rect[2])
        height_b = np.linalg.norm(rect[0] - rect[3])
        max_height = max(int(height_a), int(height_b))
        
        # 目标点
        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ], dtype=np.float32)
        
        # 计算透视变换矩阵
        M = cv2.getPerspectiveTransform(rect, dst)
        
        # 应用透视变换
        warped = cv2.warpPerspective(image, M, (max_width, max_height))
        
        return warped
    
    def _reduce_noise(self, image: np.ndarray) -> np.ndarray:
        """降噪处理"""
        strength = self.config.noise_reduction_strength
        
        if len(image.shape) == 3:
            # 彩色图像使用Non-local Means降噪
            h = int(10 * strength)
            return cv2.fastNlMeansDenoisingColored(image, None, h, h, 7, 21)
        else:
            # 灰度图像降噪
            h = int(10 * strength)
            return cv2.fastNlMeansDenoising(image, None, h, 7, 21)
    
    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """对比度和亮度增强"""
        contrast = self.config.contrast_factor
        brightness = self.config.brightness_factor
        
        # 应用对比度和亮度调整
        enhanced = cv2.convertScaleAbs(image, alpha=contrast, beta=(brightness - 1) * 50)
        
        # 如果是彩色图像，还可以进行CLAHE增强
        if len(image.shape) == 3:
            # 转换到LAB色彩空间
            lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # 对L通道应用CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # 合并通道并转换回BGR
            enhanced = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        else:
            # 灰度图像直接应用CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(enhanced)
        
        return enhanced
    
    def _sharpen_image(self, image: np.ndarray) -> np.ndarray:
        """图像锐化"""
        strength = self.config.sharpening_strength
        
        # 定义锐化核
        kernel = np.array([
            [-1, -1, -1],
            [-1, 9, -1],
            [-1, -1, -1]
        ]) * strength
        
        # 调整中心值以保持亮度
        kernel[1, 1] = 8 + strength
        
        # 应用锐化滤波器
        sharpened = cv2.filter2D(image, -1, kernel)
        
        # 与原图混合
        alpha = min(strength, 1.0)
        result = cv2.addWeighted(image, 1 - alpha, sharpened, alpha, 0)
        
        return result
    
    def _binarize_image(self, image: np.ndarray) -> np.ndarray:
        """图像二值化"""
        # 转为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 自适应阈值二值化
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    def _adjust_dpi(self, image: Image.Image) -> Image.Image:
        """调整图像DPI"""
        # PIL的DPI调整主要是元数据，实际分辨率需要重新计算
        current_width, current_height = image.size
        
        # 假设原始DPI为72（网页标准）
        scale_factor = self.config.output_dpi / 72
        
        new_width = int(current_width * scale_factor)
        new_height = int(current_height * scale_factor)
        
        # 使用高质量重采样
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return resized
    
    def _calculate_quality_score(self, image: np.ndarray) -> float:
        """计算图像质量评分"""
        try:
            # 转为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 计算拉普拉斯方差（清晰度指标）
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # 计算对比度
            contrast = gray.std()
            
            # 计算亮度分布
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist_norm = hist / hist.sum()
            entropy = -np.sum(hist_norm * np.log(hist_norm + 1e-7))
            
            # 综合评分 (0-100)
            sharpness_score = min(laplacian_var / 100, 100)
            contrast_score = min(contrast / 2.55, 100)
            entropy_score = min(entropy * 12.5, 100)
            
            overall_score = (sharpness_score * 0.4 + contrast_score * 0.3 + entropy_score * 0.3)
            
            return min(overall_score, 100.0)
            
        except Exception:
            return 50.0  # 默认中等质量
    
    def get_preview_comparison(self, original: Image.Image, processed: Image.Image) -> Image.Image:
        """生成原图和处理后图像的对比预览"""
        # 调整图像大小以便对比
        width = 800
        aspect_ratio = original.height / original.width
        height = int(width * aspect_ratio)
        
        # 调整两张图片到相同大小
        orig_resized = original.resize((width // 2, height), Image.Resampling.LANCZOS)
        proc_resized = processed.resize((width // 2, height), Image.Resampling.LANCZOS)
        
        # 创建对比图像
        comparison = Image.new('RGB', (width, height))
        comparison.paste(orig_resized, (0, 0))
        comparison.paste(proc_resized, (width // 2, 0))
        
        return comparison


def create_preprocessor_config(mode: str = "document", **kwargs) -> PreprocessingConfig:
    """创建预处理配置的便捷函数"""
    config = PreprocessingConfig(mode=PreprocessingMode(mode))
    
    # 应用自定义参数
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config