# `pylectra.registry` 模块

_参考资料_

**前置阅读：** [什么是插件](../../concepts/what-is-plugin.md)

插件注册表 + 装饰器。

## 12 个白名单类别

```python
CATEGORIES = (
    "generator", "exciter", "governor", "pss",
    "ode_solver", "power_flow",
    "fault", "case", "scenario", "filter",
    "small_signal", "plot",
)
```

类别白名单，不能随意添加新类别——避免插件爆炸。

## `@register(category, name)`

类装饰器：把类塞进注册表 `category/name`。

```python
from pylectra.registry import register
from pylectra.interfaces.fault import FaultEvent

@register("fault", "my_fault")
class MyFault(FaultEvent):
    def build_arrays(self):
        ...
```

**抛错**

- `ValueError` — `category` 不在白名单
- `ValueError` — `name` 已注册（除非是同一类的重复 import）

注册同时给类加两个属性：

- `cls.__plugin_category__ = category`
- `cls.__plugin_name__ = name`

## `get(category, name)`

```python
from pylectra.registry import get
cls = get("ode_solver", "scipy_dop853")
solver = cls()
```

不存在抛 `KeyError`，错误信息列出当前 category 下所有已注册名。

## `list_plugins(category=None)`

```python
from pylectra.registry import list_plugins

list_plugins("fault")
# {'fault': ['bus_fault', 'composite', 'line_trip', 'load_step']}

list_plugins()                          # 全部
# {'case': [...], 'exciter': [...], ...}
```

## `categories()`

```python
from pylectra.registry import categories
print(categories())
# ['case', 'exciter', 'fault', 'filter', 'generator',
#  'governor', 'ode_solver', 'plot', 'power_flow',
#  'pss', 'scenario', 'small_signal']
```

只返回**当前已有插件**的类别（白名单中可能某些类别空着）。

## `reset()`

```python
from pylectra.registry import reset
reset()                                 # 清空所有注册
```

**仅供测试用**。生产代码里调用会让 `import pylectra` 后续行为崩坏。

## 自动发现机制

`import pylectra` 触发：

1. **内置发现** — `pylectra.plugin_loader.discover()` 用 `pkgutil.walk_packages` 递归 import `pylectra` 所有子模块（除 `_legacy`）
2. **第三方发现** — 读 `importlib.metadata.entry_points(group="pylectra.plugins")` 并依次 import

第三方包发布插件示例：

```toml
# 你的 pyproject.toml
[project.entry-points."pylectra.plugins"]
my_extension = "my_pkg.plugins"   # 这个模块里的 @register 会被触发
```

## 注册表内部结构

```python
from pylectra.registry import _REGISTRY
# {category: {name: class}}
_REGISTRY["fault"]["bus_fault"]
# <class 'pylectra.faults.bus_fault.BusFault'>
```

> ⚠️ `_REGISTRY` 是私有 dict，**别直接改**——绕过了重名检查、注册表会失去一致性。

## 接下来读什么

- [pylectra.interfaces](interfaces.md) — 各类别 ABC
- [插件清单](../plugins-catalog.md) — 内置全部
