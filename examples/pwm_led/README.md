# PeriphX STM32F103C8T6 Breathing LED Example

> Date: 2026-07-19  
> PeriphX commit: `d0f2e30646a9754e9564c81ef6c2cde5ea771789`

This example shows how to drive a PeriphX `pwm_led` component from an STM32F103C8T6 MCU over SPI.
It demonstrates a simple breathing-light effect by sweeping the PWM duty cycle from 0% to 100% and back.

## Target platform

- MCU: STM32F103C8T6
- IDE: Keil MDK-ARM uVision 5
- Compiler: Arm Compiler 5 (Keil default "compiler version 5")
- FPGA side: PeriphX bitstream generated from the commit listed above

## What this example does

The example performs the following steps:

1. Initializes SPI1 as master in SPI Mode 0
2. Uses a manual CS pin instead of hardware NSS
3. Sends PeriphX PWM configuration frames through `periphx_device_init(...)`
4. Sweeps the LED duty cycle smoothly to create a breathing effect

The example is intentionally simple and is meant to be the first bring-up reference for PeriphX on STM32F103C8T6.

## Hardware requirements

- An STM32F103C8T6 board
- A PeriphX-capable FPGA board flashed with the matching `periphx_generated.sof`
- SPI wiring:
  - `SPI_CLK`
  - `SPI_CS_N`
  - `SPI_MOSI`
  - `SPI_MISO`
  - shared `GND`

## SPI configuration

The STM32 side uses:

- SPI Mode 0
- 8-bit transfer
- MSB first
- Manual CS control

The SPI clock is intentionally kept slow for bring-up.  
If the link is stable, you may increase the clock later.

## Project files

The example is based on the Keil project located in:

- `C:\Users\guo\Desktop\stm32_rpoject\PeriphX_test`

Important files:

- `main.c`
- `User/periphx_sdk.c`
- `User/periphx_sdk.h`

## Build instructions

1. Open the Keil project for `PeriphX_test`
2. Select **Arm Compiler 5**
3. Build the project
4. Flash the STM32F103C8T6 target

## FPGA side

Make sure the FPGA is programmed with the matching bitstream generated from the same PeriphX commit.

The generated build artifacts are stored under:

- `tests/build/mlr/dist/periphx_generated.sof`
- `tests/build/mlr/sdk/periphx_sdk.h`
- `tests/build/mlr/sdk/periphx_sdk.c`

## Expected behavior

When the setup is correct:

- The STM32 repeatedly updates the PWM duty cycle through PeriphX
- The LED should show a smooth breathing effect
- The example should not require any manual interaction after boot

## Notes

- This example is a bring-up reference, not a final production application.
- The PeriphX SDK and FPGA bitstream must match the same commit family.
- If the LED only toggles or blinks instead of breathing, check:
  - SPI mode
  - CS wiring
  - SPI clock rate
  - FPGA bitstream version
  - Whether the correct `periphx_sdk.c/.h` files are used

