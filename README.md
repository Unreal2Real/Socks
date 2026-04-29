# Socks — 厂字形态股票扫描器

A股"厂"字形态（杯柄形态/Cup-with-Handle）自动识别与扫描工具。

## 功能

- **实时扫描** — 全市场扫描，发现当前形成厂字形态的个股
- **增量扫描** — 智能状态跟踪，每天只扫需要复查的股票
- **历史回测** — 验证某段时间内形态出现的频率和分布
- **K线报告** — 自动生成带蜡烛图和标注的 HTML 报告
- **观察列表** — 跟踪接近形态但尚未完成的股票

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 增量扫描（日常使用，只扫需要复查的）
python3 main.py scan

# 全量扫描（首次或每周一次）
python3 main.py scan --full

# 回测验证（看某段时间出现了几次）
python3 main.py backtest --stocks 603135,301439 --start 2026-01-01

# 查看观察列表
python3 main.py stats
```

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
├── main.py                   # 主入口（scan / backtest / stats）
├── backtest.py               # 回测引擎
├── report.py                 # HTML 报告生成
├── config/settings.py        # 策略参数配置
├── data/
│   ├── fetcher.py            # baostock 数据接口
│   └── scan_state.py         # SQLite 扫描状态管理
├── indicators/technical.py   # 技术指标（MA, BB, 成交量）
├── patterns/factory_pattern.py # 厂字形态识别算法
├── filters/stock_filter.py   # 股票过滤（价格、成交量、ST）
└── utils/visualizer.py       # K线图可视化
```

## 数据源

使用 [baostock](http://baostock.com) 获取 A 股日线行情数据，包含：
- 沪深两市全部股票/指数
- 前复权价格
- 2007年至今的历史数据

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
