# 命令行参考

_参考资料_

```
python -m pylectra <command> [args] [options]
```

或者（如果你 `pip install pylectra` 之后入口脚本生效）：

```
pylectra <command> [args] [options]
```

## 命令一览

| 命令 | 用途 |
|---|---|
| `run` | 跑一个 YAML 配置（single / batch / cct） |
| `info` | 列出所有已注册插件 + 硬件信息 |
| `plot` | 直接出图（跑仿真或读已有 .h5） |

## `run`

```
python -m pylectra run <config.yaml> [-O KEY=VALUE]... [--verbose N] [--no-plot]
```

**参数**

| 参数 | 说明 |
|---|---|
| `<config.yaml>` | 必填，YAML 配置文件路径 |
| `-O KEY=VALUE` | 覆盖 YAML 字段（值是 JSON）；可重复 |
| `--verbose 0/1/2` | 覆盖 YAML 里的 verbose |
| `--no-plot` | 强制 plot=false |

**示例**

```bash
# 基本
python -m pylectra run examples/single_case39.yaml

# 覆盖单字段
python -m pylectra run examples/single_case39.yaml \
    -O 'fault.params.duration=0.10' \
    -O 'solver.kind="scipy_dop853"'

# 静默 + 不弹图
python -m pylectra run examples/batch_case39.yaml --verbose 0 --no-plot
```

**退出码**

- `0`：成功
- `1`：配置错误（YAML 语法 / 未知 plugin / 必填字段缺失）
- `2`：仿真失败（潮流不收敛 / 求解器异常等）

## `info`

```
python -m pylectra info [--category CAT] [--hardware]
```

**参数**

| 参数 | 说明 |
|---|---|
| `--category CAT` | 只列某一类别（如 `generator`、`fault`） |
| `--hardware` | 包含 CPU / 内存 / GPU 信息 |

**示例**

```bash
# 全部插件
python -m pylectra info

# 只看故障类型
python -m pylectra info --category fault
# fault: ['bus_fault', 'composite', 'line_trip', 'load_step']

# 含硬件信息
python -m pylectra info --hardware
```

## `plot`

```
python -m pylectra plot <source> --type TYPE --output FILE \
    [--format FORMATS] [-O KEY=VALUE]...
```

**参数**

| 参数 | 说明 |
|---|---|
| `<source>` | YAML 配置（自动跑仿真）/ 已有 .h5 / batch 输出目录 |
| `--type TYPE` | 插件名（见 [plugins-catalog](plugins-catalog.md#plots)） |
| `--output FILE` | 输出文件名 |
| `--format FORMATS` | 逗号分隔，如 `pdf,svg,png` |
| `-O KEY=VALUE` | 给画图函数传额外 kwargs（值是 JSON） |

**示例**

```bash
# 跑 case39 + 画转子角，输出 PDF
python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf

# 多种格式同时输出
python -m pylectra plot examples/single_case39.yaml \
    --type overview --output overview --format pdf,svg,png

# 直接读已存盘 H5
python -m pylectra plot ./out_batch/sample_000003.h5 \
    --type rotor_angles --output sample3.pdf

# 拓扑图按电压上色
python -m pylectra plot examples/single_case39.yaml \
    --type topology --output topo.pdf \
    -O 'color_by="vm"'

# batch 结果直方图
python -m pylectra plot ./out_batch \
    --type histogram --output hist.pdf \
    -O 'column="filter_angle_stability_metric"' \
    -O 'bins=40'
```

## 全局选项

| 选项 | 说明 |
|---|---|
| `-h` / `--help` | 显示帮助 |
| `--version` | 显示 pylectra 版本号 |

## 环境变量

| 变量 | 说明 |
|---|---|
| `JOBLIB_TEMP_FOLDER` | joblib worker 的临时目录（Windows 非 ASCII 用户名必须设） |
| `OPENBLAS_NUM_THREADS` / `MKL_NUM_THREADS` | 限制 BLAS 线程数 |
| `PYTORCH_CUDA_ALLOC_CONF` | torch CUDA 分配器（高级） |
| `PYLECTRA_LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING`（高级） |

## 重定向输出

```bash
# stdout 写到文件
python -m pylectra run examples/batch_case39.yaml > run.log

# stdout + stderr 都写到同一文件
python -m pylectra run examples/batch_case39.yaml > run.log 2>&1

# 后台跑（Linux/macOS）
nohup python -m pylectra run examples/batch_case39.yaml > run.log 2>&1 &
```

## 接下来读什么

- [YAML schema](yaml-schema.md) — 配置文件字段
- [插件清单](plugins-catalog.md) — `kind` 取值
