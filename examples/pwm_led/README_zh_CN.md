# PeriphX STM32F103C8T6 呼吸灯示例

> 日期：2026-07-19  
> PeriphX commit：`d0f2e30646a9754e9564c81ef6c2cde5ea771789`

本示例演示如何在 STM32F103C8T6 MCU 上，通过 SPI 驱动 PeriphX 的 `pwm_led` 组件，实现 LED 的呼吸灯效果。
示例会平滑地将 PWM 占空比从 0% 扫到 100%，再从 100% 扫回 0%。

## 目标平台

- MCU：STM32F103C8T6
- IDE：Keil MDK-ARM uVision 5
- 编译器：Arm Compiler 5（Keil 默认的 "compiler version 5"）
- FPGA 侧：使用与本示例对应 commit 生成的 PeriphX bitstream

## 示例功能

本示例完成以下工作：

1. 将 SPI1 初始化为主机模式，使用 SPI Mode 0
2. 采用手动 CS 引脚控制，不使用硬件 NSS
3. 通过 `periphx_device_init(...)` 发送 PeriphX 的 PWM 配置帧
4. 连续平滑地调整 LED 占空比，形成呼吸效果

这个示例保持尽可能简单，适合作为 STM32F103C8T6 首次联调 PeriphX 的参考。

## 硬件需求

- 一块 STM32F103C8T6 开发板
- 一块已经烧录匹配 `periphx_generated.sof` 的 PeriphX FPGA 板
- SPI 连线：
  - `SPI_CLK`
  - `SPI_CS_N`
  - `SPI_MOSI`
  - `SPI_MISO`
  - 公共 `GND`

## SPI 配置

STM32 侧使用以下配置：

- SPI Mode 0
- 8 位传输
- MSB first
- 手动控制 CS

为了方便首轮调试，SPI 时钟被刻意设置得比较慢。  
如果链路稳定，后续可以再提高频率。

## 工程文件

本示例基于以下 Keil 工程：

- `C:\Users\guo\Desktop\stm32_rpoject\PeriphX_test`

关键文件包括：

- `main.c`
- `User/periphx_sdk.c`
- `User/periphx_sdk.h`

## 编译步骤

1. 打开 `PeriphX_test` 对应的 Keil 工程
2. 选择 **Arm Compiler 5**
3. 编译工程
4. 烧录 STM32F103C8T6

## FPGA 侧

请确认 FPGA 烧录的是与当前 PeriphX commit 匹配的 bitstream。

生成产物位于：

- `tests/build/mlr/dist/periphx_generated.sof`
- `tests/build/mlr/sdk/periphx_sdk.h`
- `tests/build/mlr/sdk/periphx_sdk.c`

## 期望现象

当硬件连接正确时：

- STM32 会通过 PeriphX 周期性更新 PWM 占空比
- LED 会呈现平滑的呼吸效果
- 上电后无需额外手动干预

## 注意事项

- 本示例是联调参考，不是最终量产应用
- PeriphX SDK 和 FPGA bitstream 必须来自同一套 commit 体系
- 如果 LED 不是呼吸，而是只亮灭闪烁，请优先检查：
  - SPI 模式是否正确
  - CS 引脚是否接对
  - SPI 时钟频率是否过高或过低
  - FPGA bitstream 是否为对应版本
  - 是否使用了正确的 `periphx_sdk.c/.h`

