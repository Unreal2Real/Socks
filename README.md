# Socks — 厂字形态股票扫描器

A股"厂"字形态（杯柄形态/Cup-with-Handle）自动识别与扫描工具。

## 功能

- **实时扫描** — 全市场扫描，发现当前形成厂字形态的个股
- **增量扫描** — 智能状态跟踪，每天只扫需要复查的股票
- **历史回测** — 验证某段时间内形态出现的频率和分布
- **K线报告** — 自动生成带蜡烛图和标注的 HTML 报告
- **观察列表** — 跟踪接近形态但尚未完成的股票
- **多数据源** — 支持混合数据源，兼顾速度与实时性

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 增量扫描（默认使用混合数据源）
python3 main.py scan

# 指定数据源
python3 main.py scan --source hybrid    # 混合模式（优先本地）
python3 main.py scan --source baostock # Baostock API
python3 main.py scan --source tdx      # 本地通达信数据

# 全量扫描
python3 main.py scan --full

# 回测验证
python3 main.py backtest --stocks 603135,301439 --start 2026-01-01

# 查看观察列表
python3 main.py stats
```

## 数据源说明

### 混合模式 (hybrid) - 默认

- **日线数据**：优先使用通达信本地文件（速度快，离线可用）
- **实时数据**：通过 MOOTDX 获取分钟线和实时报价
- **备用数据源**：本地数据缺失时自动切换到 Baostock API

### Baostock API

- 网络获取，数据延迟 T+1
- 完全免费，无需本地软件
- 适合没有通达信的环境

### 通达信本地数据

- 读取本地 `.day` 文件，毫秒级响应
- 需要安装通达信软件并保持数据更新
- 支持离线扫描，不受网络影响

## 什么是"厂"字形态？

厂字形态是经典技术分析形态，形似汉字"厂"：

```
      ┌──────────┐
     ╱            ╲
    ╱  上涨段      ╲────────  横盘整理
   ╱                ╲
  ╱                  ╲
```

1. **上涨段（竖）** — 股价经历一轮明显上涨（通常 >15%）
2. **横盘整理（横）** — 随后进入窄幅震荡、缩量盘整，布林带收窄
3. **形态完成** — 横盘结束后放量突破，形成买入信号

## 项目结构

```
Socks/
├── main.py                      # 主入口（scan / backtest / stats）
├── backtest.py                  # 回测引擎
├── report.py                    # HTML 报告生成
├── CHANGELOG.md                 # 更新日志
├── config/settings.py           # 策略参数配置
├── data/
│   ├── fetcher.py               # 原始数据接口（兼容旧版）
│   ├── scan_state.py            # SQLite 扫描状态管理
│   └── providers/               # 数据抽象层
│       ├── __init__.py          # DataProvider 接口定义
│       ├── baostock_provider.py # Baostock API 实现
│       ├── tdx_provider.py      # TDX 本地文件实现
│       ├── hybrid_provider.py   # 混合数据源实现
│       └── factory.py           # 数据源工厂
├── indicators/technical.py      # 技术指标（MA, BB, 成交量）
├── patterns/factory_pattern.py  # 厂字形态识别算法
├── filters/stock_filter.py      # 股票过滤（价格、成交量、ST）
└── utils/visualizer.py          # K线图可视化
```

## 配置说明

编辑 `config/settings.py`：

```python
DATA_SOURCE_CONFIG = {
    'default': 'hybrid',           # 默认数据源
    'tdx_path': 'C:/zd_zsone',     # 通达信安装路径
    'fallback_enabled': True,      # 启用故障转移
}
```

## 状态管理策略

扫描结果会存入 SQLite 数据库，每只股票标记为不同状态，按间隔复查：

| 状态 | 含义 | 下次复查 |
|------|------|---------|
| `no_pattern` | 没有形态特征 | 7天后 |
| `watching_uptrend` | 上涨中，涨幅不足 | 3天后 |
| `watching_consolidation` | 盘整观察中，快成了 | 每天 |
| `matched` | 已匹配形态 | 5天后 |
| `error` | 数据异常 | 明天 |

这样每天只需扫描几十只股票，而非全市场五千多只。

## License

MIT