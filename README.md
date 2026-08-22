[简体中文](README_zh_CN.md) | [English](README.md)

# PeriphX

PeriphX is a configurable FPGA peripheral framework for MCU developers.

The current repository state already contains a working end-to-end baseline and a verified generated UART component:

- MCU talks to the FPGA over SPI
- The FPGA parses fixed-size frames and routes requests to services
- `mlr` generates the RTL, SDK, service map, and Quartus project artifacts
- `pwm_led` remains the reference bring-up component
- `uart` is implemented as a PeriphX component with runtime configuration and fixed TX/RX FIFOs

## Current Status

The current baseline is hardware-validated and should be treated as the
starting point for further development.

- SPI slave, frame parser, and router are implemented
- `pwm_led` is the reference service path
- `uart` is integrated with `mlr` code generation and generated SDK wrappers
- UART supports generated default configuration plus MCU-side runtime configuration
- UART has been validated with Verilator testbenches, functional coverage, and line coverage checks
- The generated SDK is ready for MCU integration
- Generated artifacts are written under `userSpace/dist`

What is still true:

- The framework is not feature-complete
- Component support is being expanded from `pwm_led` and `uart` toward more common peripherals
- Service IDs are assigned in manifest order during the build

## Repository Layout

- `components/core/`
  - Core RTL blocks: `spi_slave`, `protocol_parse`, `data_router`
- `components/pwm_led/`
  - Reference component used for end-to-end bring-up
- `components/uart/`
  - Generated UART component with runtime configuration, TX/RX FIFOs, SDK wrappers, and Verilator tests
- `userSpace/manifest.yaml`
  - Source of truth for the current build
- `mlr/`
  - Python generator that reads the manifest and emits RTL / SDK / Quartus
    inputs
- `userSpace/dist/`
  - Generated artifacts; this is the output directory for the current build
- `docs/frame_format.txt`
  - Canonical frame-format note for the current protocol contract

## Build Flow

```mermaid
flowchart LR
    M["userSpace/manifest.yaml"] --> G["mlr"]
    G --> RTL["userSpace/dist/rtl/periphx_generated.v"]
    G --> SDK["userSpace/dist/sdk/periphx_sdk.c/.h"]
    G --> MAP["userSpace/dist/meta/service_map.json"]
    G --> SOF["userSpace/dist/periphx_generated.sof"]
    MCU["MCU application"] --> SDK_USE["generated SDK"]
    SDK_USE --> TRANSPORT["platform transport callback"]
    TRANSPORT --> FPGA["spi_slave -> protocol_parse -> data_router -> component"]
```

The `manifest.yaml` file defines the components for a given build. `mlr`
turns that into:

- FPGA RTL
- MCU SDK headers and source
- Service ID mapping metadata
- Quartus project input and bitstream

## MCU Integration

The generated SDK is platform-agnostic. MCU developers provide a transport
callback and a user-context pointer.

```c
typedef int (*periphx_transport_fn)(
    void *user,
    const uint8_t *tx,
    uint8_t *rx,
    size_t len
);

typedef struct {
    periphx_transport_fn transfer;
    void *user;
} periphx_device_t;
```

`user` is an opaque pointer that the SDK passes back to your transport
function. It is typically used to store platform-specific state such as:

- SPI peripheral handle
- CS pin information
- DMA or lock state
- any other transport metadata

Minimal usage pattern:

```c
periphx_device_t dev;
periphx_device_init(&dev, my_transport, &my_context);

uint32_t response = 0;
periphx_pwm_led1_set_sys_cnt_prds(&dev, 50000000u, &response);
periphx_pwm_led1_set_sys_cnt_duty(&dev, 25000000u, &response);
```

The generated SDK exposes:

- Generic helpers such as `periphx_transfer_frame`
- Typed helpers such as `periphx_call_u32`
- Component-specific wrappers generated from `manifest.yaml`

For UART instances, the generated SDK also exposes a typed runtime configuration API based on `periphx_uart_config_t`, so MCU code can configure baud rate, data bits, parity, and stop bits without manually packing the payload.

## Build

From the repository root:

```powershell
python -m mlr build --generate-only
python -m mlr build
```

`--generate-only` writes the RTL, SDK, and service map without running
Quartus. `python -m mlr build` performs the full flow and copies the resulting
bitstream into:

- [`userSpace/dist/periphx_generated.sof`](userSpace/dist/periphx_generated.sof)

## Notes

- The current build is validated around the `pwm_led` reference path and the generated UART component path.
- If you change the order of components or services in `manifest.yaml`, the
  generated service IDs will change because IDs are assigned during the build.
- Generated files live under `userSpace/dist`; do not edit them by hand.
- For day-to-day work, treat `userSpace/manifest.yaml` as the build input and
  `userSpace/dist/` as disposable output.
- Future development priorities are tracked in [`MLR_TBD.md`](MLR_TBD.md). Current planned directions include IRQ support, a fuller I2C master, GPIO, SPI master, Timer, more tests/CI, and more examples.

## Contributing

Issues, ideas, and implementation help are welcome.

If you want to discuss the project, contact:

**[ghz2985715538@gmail.com](mailto:ghz2985715538@gmail.com)**
