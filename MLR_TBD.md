# MLR_TBD

## 背景

当前 `UART_dev` 分支已经完成 UART 方案 2 的 RTL 和测试样例：

- UART 外设语义：单字节 TX/RX 缓冲 + 状态寄存器。
- UART 引脚：`uart_rxd` / `uart_txd`。
- UART services：`set_baudrate`、`set_enable`、`write_tx`、`read_rx`、`get_status`、`clear_status`。
- 测试样例全部位于 `tests/` 下。

但当前仓库另有 `refactor/mlr-python-split` 分支，已经把原来的单文件 `mlr/codegen.py` 拆分为模块化结构。因此本分支不应长期保留对单文件 `mlr/codegen.py` 的大块 UART 生成器改动，避免后续合并时与 Python 重构分支产生大冲突。

## 当前分支处理策略

本分支采用“方案 B”：

1. 保留 UART RTL、interface、core lint 修正和 tests。
2. 撤销当前分支中临时写入的 `mlr/*.py` 改动。
3. 后续在 `refactor/mlr-python-split` 上按模块化结构重新接入 UART 生成器。

这意味着：在迁移完成前，本分支的 UART RTL 和 TB 是有效的，但 `mlr` 默认生成器仍只支持当前基线已有组件。需要 UART 进入 `mlr` 生成范围时，应先完成下方迁移。

## 需要迁移到 `refactor/mlr-python-split` 的功能

### 1. 新增 UART 组件生成模块

在重构分支新增：

```text
mlr/codegen/rtl/components/uart.py
```

建议导出以下函数：

```python
def emit_uart_adapter() -> list[str]:
    ...


def emit_uart_instance(spec: ProjectSpec, component: ComponentSpec) -> list[str]:
    ...


def is_uart_output_pin(pin_name: str) -> bool:
    return pin_name == "uart_txd"
```

`emit_uart_adapter()` 负责生成 `periphx_uart_adapter`。该 adapter 需要实例化 RTL 中的 `uart_core`，并实现以下 service 行为：

| service | 语义 |
|---|---|
| `set_baudrate` | payload 为真实波特率；非法值返回 `MSG_ERROR + 0x0000_0011` |
| `set_enable` | payload bit0 控制 UART 使能 |
| `write_tx` | enabled 且 tx_ready 时写 1 字节；否则返回 `MSG_ERROR + 0x0000_0010` |
| `read_rx` | 返回 RX 缓冲字节；若 `rx_valid=1`，读取后清 `rx_valid` |
| `get_status` | 返回状态寄存器 |
| `clear_status` | 按 payload bit 清除 sticky 状态 |

状态位定义：

```text
bit0  enabled
bit1  tx_busy
bit2  tx_ready
bit3  tx_done
bit4  rx_valid
bit5  rx_overrun
bit6  frame_error，初版恒 0
bit7  baud_valid
```

错误码定义：

```text
ERR_BAD_TYPE                  = 0x0000_0002
ERR_UART_TX_BUSY_OR_DISABLED  = 0x0000_0010
ERR_UART_BAD_BAUDRATE         = 0x0000_0011
```

### 2. 修改重构分支的 top 生成器

修改：

```text
mlr/codegen/rtl/top.py
```

需要：

1. import UART 生成函数：

```python
from mlr.codegen.rtl.components.uart import (
    emit_uart_adapter,
    emit_uart_instance,
    is_uart_output_pin,
)
```

2. 在 `write_generated_rtl()` 的 component type dispatch 中增加：

```python
elif component_type == "uart":
    lines.extend(emit_uart_adapter())
```

3. 在 `emit_top_module()` 的 component instance dispatch 中增加：

```python
elif component.component_type == "uart":
    lines.extend(emit_uart_instance(spec, component))
```

4. 在 `is_output_pin()` 中增加：

```python
if component.component_type == "uart":
    return is_uart_output_pin(pin_name)
```

### 3. 保留或重做 repo root 查找能力

当前测试 fixture 放在：

```text
tests/fixtures/uart_workspace/manifest.yaml
```

如果 `mlr` 仍使用：

```python
repo_root = workspace_dir.parent
```

则 `--workspace tests/fixtures/uart_workspace` 会把 `tests/fixtures` 误判为 repo root，导致找不到 `components/`。

重构分支需要二选一：

#### 推荐：加入 repo root 查找 helper

在 `mlr/project.py` 或专门 helper 中增加：

```python
def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "components").is_dir() and (candidate / "mlr").is_dir():
            return candidate

    return start.resolve().parent
```

然后让 `load_project_spec()` 和 `builder._mlr_output_root()` 使用该 repo root。

#### 不推荐：改变测试 workspace 位置

把测试 workspace 放到 repo root 直接子目录可以规避该问题，但这不符合“测试样例全部放在 `tests/`”的约束。

### 4. Verilator lint 辅助修正

当前 UART 验证中，`-Wall` 会暴露少量已有宽度/空连接问题。建议保留以下已修正方向：

- `components/core/protocol_parse.v`：`tx_index` 是 4 bit，复位/清零常量应使用 `4'd0`。
- `components/core/data_router.v`：`req_service_id_r < NUM_SLOTS` 比较时，显式扩展 `req_service_id_r` 宽度。
- generated RTL 中如需在 `-Wall` 下 lint，可用命名 wire 接住 `cs_active/cs_start/cs_end/req_ready`，或在生成文件头部针对 generated unused 噪声加 Verilator lint pragma。

## 迁移后需要跑的验证

### 1. UART 全量测试

```bash
bash tests/tb/uart/run_all_uart_tests.sh
```

期望输出：

```text
UART core strict test passed
UART adapter strict test passed
All UART tests passed
```

### 2. 默认 manifest 生成

```bash
python -m mlr build --generate-only
```

### 3. 默认 PWM 顶层 lint

```bash
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /mnt/c/Users/hzguo/Desktop/PeriphX/PeriphX && verilator --lint-only -Wall --top-module periphx_top components/core/*.v components/pwm_led/rtl/*.v tests/build/mlr/rtl/periphx_generated.v'
```

### 4. UART fixture 顶层 lint

```bash
python -m mlr build --workspace tests/fixtures/uart_workspace --generate-only
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /mnt/c/Users/hzguo/Desktop/PeriphX/PeriphX && verilator --lint-only -Wall --top-module periphx_top components/core/*.v components/uart/rtl/uart_core.v components/uart/rtl/uart_tx.v components/uart/rtl/uart_rx.v tests/build/mlr/rtl/periphx_generated.v'
```

## 注意事项

- 不要把当前分支中临时写入的单文件 `mlr/codegen.py` UART 逻辑直接合进重构分支。
- `tests/tb/uart/tb_uart_adapter.cpp` 依赖 generated `periphx_uart_adapter`，因此在 Python 迁移完成前，adapter TB 可能无法通过。
- `tests/tb/uart/tb_uart_core.cpp` 只依赖 UART RTL core，应该不受 Python 迁移影响。
- `tests/fixtures/uart_workspace/manifest.yaml` 是为了验证 `mlr --workspace` 能从 tests 内 manifest 生成 UART 工程。
