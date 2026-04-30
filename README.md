# 厂字形态股票扫描器

基于 Python 的 A 股「厂」字形态自动扫描工具。

**核心功能：** 扫描全市场沪深 A 股主板股票，自动识别符合「厂」字技术形态（上涨→盘整）的股票。

## 快速开始

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://localhost:5555`

## 架构

```
app.py              ← Flask Web 入口
├── data/
│   ├── fetcher.py  ← 三层数据源（TDX本地 → CSV缓存 → Baostock API）
│   └── cache.py    ← 线程安全缓存
├── pattern/
│   └── recognizer.py ← 倒序扫描形态识别
├── scanner/
│   └── engine.py   ← 后台异步扫描引擎
└── templates/
    └── index.html  ← 单页 UI
```

## 数据获取优先级

1. 通达信本地 `.day` 文件（微秒级）
2. 本地 CSV 缓存（毫秒级，增量更新）
3. Baostock API（秒级，3次重试+指数退避）

## 形态识别逻辑

从最近的数据往前扫描：
1. **上涨起点**：连续 5 天 MA5 > MA10 > MA20 多头排列
2. **上涨段**：维持多头排列，涨幅 ≥ 15%，收盘跌破 MA5 确认结束
3. **盘整段**：布林带宽收窄 + 振幅降低 + 成交量萎缩

## 技术栈

| 层 | 技术 |
|----|------|
| 数据源 | Baostock, mootdx |
| 数据处理 | Pandas, NumPy |
| Web | Flask |
| 前端 | Vanilla JS + Lightweight Charts |
| 缓存 | CSV 文件 |

## 配置

编辑 `_config.py` 调整识别参数：

```python
FACTORY_PATTERN = {
    'uptrend_gain': 0.15,        # 上涨段最少涨幅
    'consolidation_days_min': 10, # 盘整最少天数
    'consolidation_days_max': 40, # 盘整最多天数
    'bandwidth': 0.20,           # 布林带宽阈值
    'volatility': 0.20,          # 波动率阈值
    'volume_ratio': 0.6,         # 量比阈值
}
```
