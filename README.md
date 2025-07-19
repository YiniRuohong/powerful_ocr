# Powerful OCR - 智能PDF文字识别工具

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)

一个功能强大的多格式文档OCR工具，采用灵活的多OCR架构：支持**PDF、图片、Word、PowerPoint**等多种文件格式，集成**阿里云DashScope**、**Mistral**、**自定义OpenAI格式**等多种OCR服务 + **Google Gemini智能纠错**，提供高精度的文字识别和智能格式化功能。

## ✨ 主要特性

- 🔥 **多OCR服务支持**：DashScope、Mistral、自定义OpenAI格式API，可灵活选择
- 🧠 **智能纠错架构**：Gemini AI进行OCR后文本纠错与结构识别
- 📄 **多格式输入支持**：PDF、图片(JPG/PNG/TIFF/BMP/WEBP/GIF)、Word文档(DOCX/DOC)、PowerPoint(PPTX/PPT)
- 🎨 **图像预处理优化**：降噪、锐化、对比度调整、倾斜矫正、透视校正等功能
- ✨ **现代化Web界面**：磨砂玻璃设计风格，支持深色/浅色主题切换，优化信息密度
- 📋 **交互式界面**：OCR服务选择、文件选择、页数范围配置、专有名词纠错
- 📊 **实时进度追踪**：显示页数进度和Token消耗统计（分OCR和纠错）
- 📝 **Markdown输出**：自动识别文档结构并格式化为标准Markdown
- 🎯 **专有名词纠错**：支持自定义术语库进行精准纠错
- 🖥️ **多运行模式**：智能启动器支持CLI、Web界面和GUI模式
- 📁 **批量处理**：支持单文件或批量处理多个文件
- 💾 **智能缓存系统**：避免重复处理，支持断点续传和自动恢复
- 🔄 **重试机制**：智能重试策略，提高处理成功率和系统稳定性

## 🚀 快速开始

### 系统要求

- **Python**: ≥3.13 (项目使用最新特性)
- **Poppler**: PDF处理依赖
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/YiniRuohong/powerful_ocr.git
   cd powerful_ocr
   ```

2. **安装依赖**
   ```bash
   uv sync
   ```

3. **配置API密钥**
   
   复制 `.env.example` 为 `.env` 并配置API密钥：
   ```bash
   cp .env.example .env
   ```
   
   编辑 `.env` 文件，配置所需的API服务：
   ```env
   # Gemini纠错服务 (必需)
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_BASE_URL=your_gemini_base_url_here
   
   # OCR服务 (至少配置一个)
   DASHSCOPE_API_KEY=your_dashscope_api_key_here
   MISTRAL_API_KEY=your_mistral_api_key_here
   CUSTOM_OCR_API_KEY=your_custom_ocr_api_key_here
   CUSTOM_OCR_BASE_URL=your_custom_ocr_base_url_here
   ```

4. **准备PDF文件**
   
   将PDF文件放入 `input/` 目录（程序会自动创建）

## 📖 使用方法

### 本地运行

#### 智能启动器（推荐）

```bash
# 自动选择最佳运行模式
python launcher.py

# 强制使用命令行模式
python launcher.py cli

# 强制使用Web界面模式
python launcher.py web

# 强制使用图形界面模式
python launcher.py gui
```

#### 直接运行

```bash
# 命令行模式（交互式）
python main.py

# Web界面模式
python backend.py

# 图形界面模式
python gui_main.py
```

### 🐳 Docker部署

#### 快速启动

```bash
# 使用docker-compose一键启动
docker-compose up -d

# 访问Web界面
open http://localhost:8000
```

#### 手动Docker构建

```bash
# 构建镜像
docker build -t powerful-ocr .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/ocr_output:/app/ocr_output \
  -v $(pwd)/terminology:/app/terminology \
  --env-file .env \
  --name powerful-ocr \
  powerful-ocr
```

#### 从GitHub Registry拉取

```bash
# 拉取最新镜像
docker pull ghcr.io/YiniRuohong/powerful-ocr:latest

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/ocr_output:/app/ocr_output \
  -v $(pwd)/terminology:/app/terminology \
  --env-file .env \
  --name powerful-ocr \
  ghcr.io/YiniRuohong/powerful-ocr:latest
```

### 使用流程

1. **选择OCR服务**
   - 程序启动时显示可用的OCR服务
   - 选择最适合的OCR提供商（DashScope/Mistral/自定义）

2. **配置图像预处理**（推荐）
   - **不处理**：保持原始图像，适合高质量扫描件
   - **基础处理**：轻量级降噪和锐化，适合一般文档
   - **文档优化**：专为扫描文档优化，包含倾斜矫正和二值化
   - **照片优化**：适合手机拍照的文档，包含透视矫正
   - **激进处理**：最大化OCR效果，适合低质量图像

3. **选择专有名词文件**（可选）
   - 在 `terminology/` 目录放置 `.txt` 文件
   - 每行一个专有名词，用于提高纠错精度

4. **选择PDF文件**
   - 程序自动扫描 `input/` 目录
   - 支持单文件或批量处理

5. **设置页数范围**
   - 自动检测PDF总页数
   - 灵活配置处理范围

6. **查看处理结果**
   - `ocr_output/` 目录中查看结果
   - 单页文件：`{文件名}_page_{页码}.md`
   - 合并文件：`{文件名}_combined.md`

## 📁 项目结构

```
powerful_ocr/
├── main.py              # 核心OCR处理程序
├── backend.py           # FastAPI Web服务器
├── format_processor.py  # 多格式文件处理模块
├── image_preprocessor.py # 图像预处理模块
├── gui_main.py          # 图形界面版本
├── launcher.py          # 智能启动器
├── web/                 # Web界面文件
├── input/               # 多格式文件输入目录
├── terminology/         # 专有名词文件目录
├── ocr_output/          # 处理结果输出目录
├── .env                 # API配置文件
├── CLAUDE.md           # 开发指南
└── README.md           # 项目说明
```

## 🔧 配置说明

### API配置

#### 必需配置
| 配置项 | 说明 | 必需 |
|--------|------|------|
| `GEMINI_API_KEY` | Google Gemini API密钥 | ✅ |
| `GEMINI_BASE_URL` | Gemini API服务地址 | ✅ |

#### OCR服务配置（至少选择一个）
| 配置项 | 说明 | 服务商 |
|--------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云DashScope API密钥 | 阿里云 |
| `MISTRAL_API_KEY` | Mistral API密钥 | Mistral AI |
| `MISTRAL_BASE_URL` | Mistral API地址（可选，默认官方API） | Mistral AI |
| `CUSTOM_OCR_API_KEY` | 自定义OCR服务API密钥 | 自定义 |
| `CUSTOM_OCR_BASE_URL` | 自定义OCR服务地址 | 自定义 |

### 专有名词配置

在 `terminology/` 目录创建 `.txt` 文件，每行一个专有名词：

```text
人工智能
机器学习
深度学习
神经网络
```

## 📊 功能特性详解

### 多OCR服务架构优势

1. **阿里云DashScope**: 专业OCR模型，高精度文字识别，特别适合中英文混合文档
2. **Mistral Pixtral**: 强大的多模态模型，优秀的多语言支持和复杂布局理解
3. **自定义服务**: 灵活支持GPT-4V、Claude 3等任何OpenAI兼容的视觉API
4. **Gemini纠错**: 智能错误修正和结构识别，统一的后处理流程

### OCR服务选择指南

- **精度优先**: 推荐DashScope，专门优化的OCR模型
- **多语言文档**: 推荐Mistral，强大的多模态理解能力
- **成本控制**: 可选择性价比最优的服务
- **特殊需求**: 使用自定义服务接入专用模型

### 实时进度监控

```
🔧 OCR服务: Mistral (pixtral-12b-2409)
处理 document.pdf [3/10页] [Token: 5,678]
📊 第 3 页 OCR Token消耗: 2,100 (输入: 1,800, 输出: 300)
📊 第 3 页 Gemini Token消耗: 1,450 (输入: 950, 输出: 500)
✓ 第 3 页处理完成
```

### 智能格式化

- 自动识别标题层级（H1-H6）
- 保持段落结构和换行
- 识别列表、引用等特殊格式
- 输出标准Markdown格式

### 智能缓存与重试系统

#### 缓存机制
- **智能缓存**：基于文件内容、处理配置、OCR服务等生成唯一缓存键
- **自动管理**：支持缓存大小限制、过期时间管理、自动清理
- **断点续传**：支持处理中断后的自动恢复，避免重复处理
- **缓存统计**：实时显示缓存使用情况、命中率等统计信息

#### 重试机制
- **智能分类**：自动识别错误类型（网络错误、API限流、超时等）
- **指数退避**：采用指数退避策略，避免频繁重试
- **熔断器**：防止服务故障时的连锁反应
- **恢复状态**：保存处理进度，支持任务恢复和状态查询

#### 缓存管理
```bash
# 查看缓存统计
python cache_cli.py stats

# 清理过期缓存
python cache_cli.py cleanup

# 清空所有缓存
python cache_cli.py clear

# 查看恢复状态
python cache_cli.py recovery
```

## 🛠️ 开发相关

### 包管理

```bash
# 安装依赖
uv sync

# 添加新依赖
uv add <package-name>

# 更新依赖
uv sync --upgrade
```

### 虚拟环境

```bash
# 激活虚拟环境（如需要）
source .venv/bin/activate
```

### 🚀 CI/CD & 自动部署

项目配置了GitHub Actions自动构建和部署流程：

#### 自动构建Docker镜像

每次推送代码到主分支时，自动：
1. 构建Docker镜像
2. 运行测试
3. 推送到GitHub Container Registry
4. 创建版本标签

#### 部署到云服务器

```bash
# 在服务器上拉取最新镜像并重启
docker-compose pull
docker-compose up -d
```

#### 环境变量配置

在GitHub仓库的Settings -> Secrets中配置以下环境变量：

- `DOCKER_USERNAME`: Docker Hub用户名
- `DOCKER_PASSWORD`: Docker Hub密码
- `GHCR_TOKEN`: GitHub Container Registry访问令牌

#### 版本管理

```bash
# 创建新版本标签
git tag v1.0.0
git push origin v1.0.0

# 自动触发构建并推送到registry
```

## 📈 性能优化

- 支持300 DPI高清PDF转换
- 智能图像压缩和格式优化
- 流式API调用减少内存占用
- 批量处理提高效率

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 版本历史

- **v3.2.0** - 全新现代化Web界面：磨砂玻璃设计风格、深色/浅色主题切换、优化信息密度、智能缓存管理
- **v3.1.0** - 新增图像预处理优化功能，支持降噪、锐化、对比度调整、倾斜矫正、透视校正
- **v3.0.0** - 多OCR服务架构，支持DashScope/Mistral/自定义服务，GUI界面增强
- **v2.0.0** - 双AI架构，实时Token统计，Markdown输出
- **v1.0.0** - 基础OCR功能

## 📄 许可证

本项目基于 MIT 许可证开源 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🆘 常见问题

### Q: 没有可用的OCR服务？
A: 检查 `.env` 文件，确保至少配置了一个OCR服务的API密钥（DASHSCOPE_API_KEY、MISTRAL_API_KEY或自定义服务）

### Q: 如何选择OCR服务？
A: 
- **中英文文档**: 推荐DashScope，专业OCR模型精度高
- **多语言文档**: 推荐Mistral，多模态理解能力强
- **成本控制**: 比较各服务token价格选择最优方案
- **特殊需求**: 使用自定义服务接入GPT-4V等模型

### Q: Poppler安装失败？
A: 确保系统包管理器已更新，macOS用户可尝试 `brew doctor` 检查brew状态

### Q: API密钥配置错误？
A: 检查 `.env` 文件格式，确保没有多余空格和引号，参考 `.env.example` 示例

### Q: 处理大文件很慢？
A: 建议分批处理，或调整页数范围减少单次处理量

### Q: OCR识别精度不理想？
A: 
1. 尝试切换不同的OCR服务
2. 启用图像预处理优化，根据文档类型选择合适的预处理模式
3. 确保PDF文件清晰度足够
4. 使用专有名词文件提高纠错精度
5. 检查文档语言是否匹配OCR服务特长

### Q: 如何选择合适的图像预处理模式？
A:
- **高质量扫描件**: 选择"不处理"保持原始质量
- **一般扫描文档**: 选择"文档优化"，包含完整的文档处理流程
- **手机拍照文档**: 选择"照片优化"，包含透视矫正功能
- **低质量图像**: 选择"激进处理"，最大化处理效果
- **不确定**: 选择"基础处理"，适用于大多数场景

## 📋 TODO 待开发功能

### 🚀 性能与扩展性优化
- [ ] **批量并行处理**：支持多文件同时OCR处理，提升大批量文档处理效率
- [ ] **分布式处理架构**：支持多机器分布式OCR，适合企业级大规模文档处理
- [ ] **智能缓存机制**：对已处理的文档建立缓存，避免重复处理相同内容
- [ ] **增量处理模式**：支持监控文件夹变化，自动处理新增文档

### 🎯 OCR精度与质量提升
- [ ] **多模型融合识别**：同时使用多个OCR模型，通过算法融合提升识别准确率
- [ ] **自适应质量检测**：根据文档质量自动选择最适合的OCR模型和参数
- [ ] **专业领域模型**：针对医疗、法律、财务等专业领域的专用OCR模型
- [ ] **OCR结果置信度评估**：为每个识别结果提供可信度评分

### 📄 文档格式与结构增强
- [ ] **表格智能识别**：专门的表格结构识别和格式化输出
- [ ] **图表内容提取**：识别并提取图表、流程图中的文字和结构信息
- [ ] **多栏布局处理**：智能识别报纸、杂志等多栏布局文档
- [ ] **手写文字识别**：支持手写中英文的识别处理

### 🌐 多语言与国际化
- [ ] **多语言OCR支持**：扩展至日语、韩语、阿拉伯语等更多语言
- [ ] **混合语言文档**：智能识别和处理多种语言混合的文档
- [ ] **RTL语言支持**：支持从右到左的语言排版（如阿拉伯语、希伯来语）
- [ ] **界面多语言化**：Web界面支持多种显示语言

### 🤖 AI智能化功能
- [ ] **文档内容摘要**：使用AI自动生成文档摘要和关键词
- [ ] **智能分类标签**：根据文档内容自动生成分类和标签
- [ ] **内容质量评估**：AI评估OCR结果质量并提供优化建议
- [ ] **语义纠错增强**：更智能的上下文纠错，理解文档语义

### 🔧 用户体验优化
- [ ] **拖拽式批量上传**：支持文件夹拖拽和批量文件选择
- [ ] **实时预览功能**：处理过程中实时预览OCR结果
- [ ] **历史记录管理**：保存处理历史，支持重新下载和管理
- [ ] **模板和预设**：保存常用配置模板，快速应用

### 📊 数据管理与分析
- [ ] **处理统计报告**：详细的处理统计和成本分析报告
- [ ] **用户使用分析**：用户行为分析和使用模式统计
- [ ] **质量指标监控**：OCR质量指标的长期监控和趋势分析
- [ ] **API使用优化**：智能选择最优的API服务以降低成本

### 🔒 企业级功能
- [ ] **用户权限管理**：多用户、角色权限管理系统
- [ ] **API接口扩展**：提供完整的RESTful API供第三方集成
- [ ] **企业级部署**：支持Kubernetes、Docker Swarm等容器编排
- [ ] **数据安全加密**：文档传输和存储的端到端加密

### 🎨 界面与交互改进
- [x] **现代化Web界面**：磨砂玻璃设计风格，提升视觉体验和现代感
- [x] **深色主题模式**：支持深色/浅色主题切换，自动保存偏好设置
- [x] **优化信息密度**：紧凑布局设计，移除冗余元素，一屏显示所有内容
- [x] **智能缓存管理**：Web界面集成缓存统计、清理和管理功能
- [ ] **响应式设计优化**：更好的移动端和平板设备支持
- [ ] **个性化设置**：用户个人偏好设置和界面定制
- [ ] **无障碍访问**：支持屏幕阅读器等无障碍功能

### 🔌 集成与扩展
- [ ] **云存储集成**：支持Google Drive、OneDrive、Dropbox等云存储
- [ ] **办公软件插件**：开发Word、Excel等办公软件的插件
- [ ] **浏览器扩展**：Chrome、Firefox等浏览器扩展程序
- [ ] **移动应用开发**：iOS和Android原生应用

---

⭐ 如果这个项目对你有帮助，请给个Star支持！