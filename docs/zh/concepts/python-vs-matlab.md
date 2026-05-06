# 给 MATLAB 用户的 Python 入门

_初学者_

> 这页面是 cheat sheet，把电力工程师最常踩的 MATLAB → Python 概念差异列出来。

## 心理准备

Python 不是 MATLAB 的克隆——它是个**通用编程语言**，科学计算只是它的一个用法。所以：

- **没有"工作目录变量"**：变量是函数局部的（除非你显式声明 `global`），不会自己留在工作区
- **没有内建绘图窗口**：要 `import matplotlib.pyplot as plt` 才能画
- **数组不是语言原生**：要 `import numpy as np`，所有矩阵运算用 `np.array`

但反过来：

- **包管理一流**：`pip install pandapower` 一秒装好
- **生态强大**：从机器学习到 Web 服务都能写
- **免费**：不用买 license

## 索引从 0 开始（最大的坑）

| MATLAB | Python (numpy) |
|---|---|
| `x(1)` 第一个 | `x[0]` 第一个 |
| `x(end)` 最后 | `x[-1]` 最后 |
| `x(1:5)` 前 5 个 | `x[0:5]` 或 `x[:5]` 前 5 个（**不含 5**） |
| `x(end-2:end)` 后 3 个 | `x[-3:]` 后 3 个 |

**Python 的 `[a:b]` 是左闭右开**——`x[2:5]` 取的是位置 2、3、4（共 3 个）。
原因之一：`x[2:5]` 长度恰好等于 `5-2=3`，写循环时方便。

## 矩阵运算

```matlab
% MATLAB
A = [1 2 3; 4 5 6];
b = A(:, 2);          % 第 2 列
c = A * A';           % 矩阵乘
d = A .* A;           % 元素乘
```

```python
# Python with numpy
import numpy as np
A = np.array([[1, 2, 3], [4, 5, 6]])
b = A[:, 1]           # 第 2 列（索引从 0）
c = A @ A.T           # 矩阵乘（@ 是新语法）
d = A * A             # 默认就是元素乘
```

**Python 默认 `*` 是元素乘**，`@` 才是矩阵乘——和 MATLAB 反过来。

## 复数

```matlab
z = 3 + 4i;
abs(z)        % 5
angle(z)      % 0.9273 (弧度)
```

```python
z = 3 + 4j                    # Python 用 j（i 通常是循环变量）
abs(z)                        # 5.0
import numpy as np
np.angle(z)                   # 0.9272952180016122
```

## 复数矩阵 / 潮流计算

```python
import numpy as np
V = np.array([1.05 + 0.0j, 1.02 - 0.05j, 1.00 + 0.02j])
I = Y @ V                     # Y 是 numpy 复数矩阵
S = V * np.conj(I)            # 复功率
```

## 控制流

```python
# if / elif / else
if voltage > 1.10:
    print("over-voltage")
elif voltage > 1.05:
    print("warning")
else:
    print("ok")

# for（注意 range 是左闭右开）
for i in range(10):           # i = 0, 1, ..., 9
    print(i)

# while
t = 0.0
while t < 10.0:
    t += 0.01
```

**冒号 + 缩进** 表示代码块，**没有 end**。缩进必须一致（4 个空格或 1 个 Tab，二选一，**一份代码里只能用一种**）。

## 函数

```matlab
function [y, dy] = my_func(x, a)
    y = a * sin(x);
    dy = a * cos(x);
end
```

```python
def my_func(x, a):
    y = a * np.sin(x)
    dy = a * np.cos(x)
    return y, dy

y, dy = my_func(0.5, 2.0)     # 解包返回值
```

Python 函数：

- 用 `def` 定义
- 用 `return` 显式返回（多个值用元组）
- **没有"函数文件名 = 函数名"的约束** —— 一个 `.py` 里可以放任意多个函数

## 调用 pylectra：MATLAB vs Python 风格

### MATLAB 风格脚本（如果 pylectra 是 MATLAB 工具箱）

```matlab
mpc = case39;
mpopt = mpoption('alg', 'NR');
results = runpf(mpc, mpopt);

events = [0.20 1; 0.25 1];
sol = rundyn(mpc, 'case39dyn', 'fault', mpopt);
plot(sol.Time, sol.Angles);
```

### Python + pylectra 实际写法

```python
from pylectra.run import run

# YAML 把所有设置外置 → 配置即代码
out = run("examples/single_case39.yaml")
print(out.result.Time.shape, out.result.Angles.shape)

# 也可以直接传 dict
out = run({"mode": "single", "case_pf": "case39",
           "fault": {"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": 0.05}}})

# 画图
from pylectra.plotting import render
render("rotor_angles", out.result, save="angles.pdf")
```

## 常见 MATLAB → Python 函数对照

| MATLAB | Python (numpy 等) |
|---|---|
| `length(x)` | `len(x)` |
| `size(A)` | `A.shape`（元组） |
| `zeros(3,4)` | `np.zeros((3, 4))` |
| `ones(3,4)` | `np.ones((3, 4))` |
| `linspace(0,1,11)` | `np.linspace(0, 1, 11)` |
| `eig(A)` | `np.linalg.eig(A)` |
| `inv(A)` | `np.linalg.inv(A)`（**少用**，多用 `np.linalg.solve`） |
| `A \ b` | `np.linalg.solve(A, b)` |
| `disp('hi')` | `print('hi')` |
| `figure; plot(t, x)` | `plt.figure(); plt.plot(t, x); plt.show()` |
| `save('out.mat', ...)` | `np.savez('out.npz', ...)` 或 HDF5 |
| `tic; ...; toc;` | `import time; t0=time.time(); ...; print(time.time()-t0)` |

## 一些 Python 习惯

- **缩进就是语法**：4 个空格表示进入代码块；少一个空格 → SyntaxError
- **下划线命名**：函数和变量用 `snake_case`（如 `my_func`），类用 `CamelCase`（如 `MyClass`）
- **大量用列表 / 字典**：`my_list = [1, 2, 3]`、`my_dict = {"a": 1, "b": 2}`
- **打印格式**：`print(f"angle = {delta:.3f} deg")` 用 f-string

## 接下来读什么

- [你的第一次仿真](../getting-started/04-first-simulation.md) — 把 MATLAB 用户的肌肉记忆迁移到 pylectra 上
- [什么是 Python 包](what-is-python-package.md) — 包 = MATLAB 工具箱
- [5 分钟读懂 YAML](what-is-yaml.md) — pylectra 的"配置脚本"
