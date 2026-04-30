# 更新日志

## v2.0.0 - 2026-04-30

### 新增功能

1. **混合数据源模式 (Hybrid Provider)**
   - 优先使用通达信本地文件获取日线数据，速度快且离线可用
   - 支持通过 MOOTDX 获取分钟线和实时报价
   - 本地数据缺失时自动切换到 Baostock API

2. **MOOTDX 集成**
   - 支持实时行情获取
   - 支持分钟线数据查询
   - 支持通达信本地文件解析

3. **数据源切换**
   - 命令行参数 `--source` 支持三种模式：
     - `hybrid`: 混合模式（默认）
     - `baostock`: Baostock API
     - `tdx`: 本地通达信数据

### 架构改进

1. **数据抽象层**
   - 创建 `data/providers/` 目录
   - 定义 `DataProvider` 抽象接口
   - 实现多种数据源实现类

2. **工厂模式**
   - 统一数据源创建入口
   - 支持故障转移机制

### 修改文件

- `config/settings.py` - 添加数据源配置
- `data/providers/__init__.py` - 数据抽象接口
- `data/providers/baostock_provider.py` - Baostock 实现
- `data/providers/tdx_provider.py` - TDX 实现
- `data/providers/hybrid_provider.py` - 混合数据源实现
- `data/providers/factory.py` - 数据源工厂
- `main.py` - 支持 `--source` 参数
- `requirements.txt` - 添加 mootdx 依赖

### 使用示例

```bash
# 默认混合模式
python main.py scan

# 指定数据源
python main.py scan --source hybrid
python main.py scan --source baostock
python main.py scan --source tdx

# 全量扫描
python main.py scan --full --source hybrid
```

### 性能提升

- 日常扫描使用本地文件，读取速度提升 100 倍
- 分时查看按需获取，节省网络资源
- 支持离线扫描，不受网络影响

## v1.0.0 - 初始版本

- 基于 Baostock API 的厂字形态股票分析工具
- 支持股票扫描、回测、统计等功能