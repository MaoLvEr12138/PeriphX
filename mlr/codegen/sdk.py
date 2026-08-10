# @brief SDK 生成模块，负责输出 PeriphX C 语言 SDK 头文件和源文件。
# @date 2026-07-28
# @author hzguo


from __future__ import annotations

from pathlib import Path

from mlr.codegen.protocol import (
    ERROR_MSG_TYPE,
    EVENT_MSG_TYPE,
    FRAME_LEN,
    REQUEST_MSG_TYPE,
    RESPONSE_MSG_TYPE,
    TURNAROUND_BYTE,
    TURNAROUND_LEN,
)
from mlr.project import ComponentSpec, ProjectSpec, ServiceSpec, sanitize_identifier

UART_SERVICE_NAMES = ["configure", "write_byte", "read_byte", "get_status"]


# @brief 根据工程服务列表生成 PeriphX SDK 头文件。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param path SDK 头文件目标路径。
# @return 写入完成后的目标路径。
def write_sdk_header(spec: ProjectSpec, path: Path) -> Path:
    lines: list[str] = []
    lines.append("#ifndef PERIPHX_SDK_H")
    lines.append("#define PERIPHX_SDK_H")
    lines.append("")
    lines.append("#include <stdbool.h>")
    lines.append("#include <stddef.h>")
    lines.append("#include <stdint.h>")
    lines.append("")
    lines.append(f"#define PERIPHX_FRAME_LEN {FRAME_LEN}u")
    lines.append(f"#define PERIPHX_TURNAROUND_LEN {TURNAROUND_LEN}u")
    lines.append("#define PERIPHX_TRANSACTION_LEN (PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN)")
    lines.append(f"#define PERIPHX_MSG_REQUEST {REQUEST_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_RESPONSE {RESPONSE_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_EVENT {EVENT_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_ERROR {ERROR_MSG_TYPE:#x}u")
    lines.append("")
    lines.append("/*")
    lines.append(" * PeriphX transport baseline:")
    lines.append(" * The current FPGA bridge keeps a short byte-alignment window between the")
    lines.append(" * request and response halves of a transaction. The SDK therefore keeps")
    lines.append(" * CS low across a request window, three alignment bytes, and a readback")
    lines.append(" * window in a single SPI transfer.")
    lines.append(" * Once the transport contract is simplified, this helper can collapse")
    lines.append(" * back to a single-phase transfer without changing the public API.")
    lines.append(" */")
    lines.append("#define PERIPHX_DEBUG_DEFERRED_READBACK 1u")
    lines.append(f"#define PERIPHX_DEBUG_READBACK_TOKEN 0x{TURNAROUND_BYTE:02X}u")
    lines.append("")
    lines.append("typedef enum {")
    lines.append("    PERIPHX_OK = 0,")
    lines.append("    PERIPHX_ERR_IO = -1,")
    lines.append("    PERIPHX_ERR_FRAME = -2,")
    lines.append("    PERIPHX_ERR_CRC = -3,")
    lines.append("    PERIPHX_ERR_RESPONSE = -4,")
    lines.append("    PERIPHX_ERR_PARAM = -5,")
    lines.append("} periphx_status_t;")
    lines.append("")
    lines.append(
        "typedef int (*periphx_transport_fn)(void *user, const uint8_t *tx, uint8_t *rx, size_t len);"
    )
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    periphx_transport_fn transfer;")
    lines.append("    void *user;")
    lines.append("} periphx_device_t;")
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    uint8_t server_id;")
    lines.append("    uint32_t payload;")
    lines.append("    uint8_t msg_type;")
    lines.append("    uint8_t crc4;")
    lines.append("} periphx_frame_t;")
    lines.append("")
    if has_uart(spec):
        lines.extend(emit_uart_type_declarations())
        lines.append("")
    for service in spec.services:
        macro = service.c_macro_name
        lines.append(f"#define {macro} {service.service_id}u")
    lines.append("")
    lines.append("void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user);")
    lines.append(
        "int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response);"
    )
    lines.append("int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value);")
    lines.append("int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value);")
    lines.append("int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value);")
    lines.append("")
    for component in spec.components:
        if component.component_type == "uart":
            lines.extend(emit_uart_header_functions(component))
        else:
            lines.extend(emit_generic_header_functions(component.services))
    lines.append("")
    lines.append("#endif /* PERIPHX_SDK_H */")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# @brief 根据工程服务列表生成 PeriphX SDK 源文件。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param path SDK 源文件目标路径。
# @return 写入完成后的目标路径。
def write_sdk_source(spec: ProjectSpec, path: Path) -> Path:
    lines: list[str] = []
    lines.append('#include "periphx_sdk.h"')
    lines.append("")
    lines.append("static uint8_t crc4_step(uint8_t crc_in, uint8_t bit_in)")
    lines.append("{")
    lines.append("    uint8_t feedback = (uint8_t)(((crc_in >> 3) ^ bit_in) & 0x1u);")
    lines.append("    uint8_t crc_out = (uint8_t)((crc_in << 1) & 0xFu);")
    lines.append("    if(feedback) {")
    lines.append("        crc_out ^= 0x3u;")
    lines.append("    }")
    lines.append("    return (uint8_t)(crc_out & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static uint8_t crc4_byte(uint8_t crc_in, uint8_t data)")
    lines.append("{")
    lines.append("    for(int bit = 7; bit >= 0; --bit) {")
    lines.append("        crc_in = crc4_step(crc_in, (uint8_t)((data >> bit) & 0x1u));")
    lines.append("    }")
    lines.append("    return (uint8_t)(crc_in & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static uint8_t crc4_nibble(uint8_t crc_in, uint8_t data)")
    lines.append("{")
    lines.append("    for(int bit = 3; bit >= 0; --bit) {")
    lines.append("        crc_in = crc4_step(crc_in, (uint8_t)((data >> bit) & 0x1u));")
    lines.append("    }")
    lines.append("    return (uint8_t)(crc_in & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static uint8_t crc4_frame(const periphx_frame_t *frame)")
    lines.append("{")
    lines.append("    uint8_t crc = 0u;")
    lines.append("    crc = crc4_byte(crc, frame->server_id);")
    lines.append("    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 24));")
    lines.append("    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 16));")
    lines.append("    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 8));")
    lines.append("    crc = crc4_byte(crc, (uint8_t)frame->payload);")
    lines.append("    crc = crc4_nibble(crc, frame->msg_type);")
    lines.append("    return (uint8_t)(crc & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static void pack_frame(const periphx_frame_t *frame, uint8_t bytes[PERIPHX_FRAME_LEN])")
    lines.append("{")
    lines.append("    bytes[0] = frame->server_id;")
    lines.append("    bytes[1] = (uint8_t)(frame->payload >> 24);")
    lines.append("    bytes[2] = (uint8_t)(frame->payload >> 16);")
    lines.append("    bytes[3] = (uint8_t)(frame->payload >> 8);")
    lines.append("    bytes[4] = (uint8_t)frame->payload;")
    lines.append("    bytes[5] = (uint8_t)(((frame->crc4 & 0xFu) << 4) | (frame->msg_type & 0xFu));")
    lines.append("}")
    lines.append("")
    lines.append("static void unpack_frame(periphx_frame_t *frame, const uint8_t bytes[PERIPHX_FRAME_LEN])")
    lines.append("{")
    lines.append("    frame->server_id = bytes[0];")
    lines.append("    frame->payload = ((uint32_t)bytes[1] << 24) | ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 8) | (uint32_t)bytes[4];")
    lines.append("    frame->msg_type = (uint8_t)(bytes[5] & 0xFu);")
    lines.append("    frame->crc4 = (uint8_t)((bytes[5] >> 4) & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user)")
    lines.append("{")
    lines.append("    dev->transfer = transfer;")
    lines.append("    dev->user = user;")
    lines.append("}")
    lines.append("")
    lines.append("static int transfer_bytes(periphx_device_t *dev, const uint8_t *tx_bytes, uint8_t *rx_bytes, size_t len)")
    lines.append("{")
    lines.append("    if(dev->transfer == NULL) {")
    lines.append("        return PERIPHX_ERR_IO;")
    lines.append("    }")
    lines.append("    if(dev->transfer(dev->user, tx_bytes, rx_bytes, len) != 0) {")
    lines.append("        return PERIPHX_ERR_IO;")
    lines.append("    }")
    lines.append("    return PERIPHX_OK;")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response)")
    lines.append("{")
    lines.append("    uint8_t tx_bytes[PERIPHX_TRANSACTION_LEN];")
    lines.append("    uint8_t rx_bytes[PERIPHX_TRANSACTION_LEN];")
    lines.append("    periphx_frame_t tmp = *request;")
    lines.append("    tmp.msg_type &= 0xFu;")
    lines.append("    tmp.crc4 = crc4_frame(&tmp);")
    lines.append("    pack_frame(&tmp, tx_bytes);")
    lines.append("    #if PERIPHX_DEBUG_DEFERRED_READBACK")
    lines.append("    for(size_t i = 0; i < PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN; ++i) {")
    lines.append("        tx_bytes[PERIPHX_FRAME_LEN + i] = PERIPHX_DEBUG_READBACK_TOKEN;")
    lines.append("    }")
    lines.append("    #else")
    lines.append("    for(size_t i = 0; i < PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN; ++i) {")
    lines.append(f"        tx_bytes[PERIPHX_FRAME_LEN + i] = 0x{TURNAROUND_BYTE:02X}u;")
    lines.append("    }")
    lines.append("    #endif")
    lines.append("    /*")
    lines.append("     * Transaction layout:")
    lines.append("     *   - bytes 0..5  : request frame")
    lines.append("     *   - bytes 6..8  : byte-alignment window")
    lines.append("     *   - bytes 9..14 : readback frame")
    lines.append("     * The alignment window is part of the current transport contract and")
    lines.append("     * keeps the response byte boundary stable while the FPGA bridge drains")
    lines.append("     * the request through parse/router/component logic.")
    lines.append("     */")
    lines.append("    if(transfer_bytes(dev, tx_bytes, rx_bytes, PERIPHX_TRANSACTION_LEN) != PERIPHX_OK) {")
    lines.append("        return PERIPHX_ERR_IO;")
    lines.append("    }")
    lines.append("    unpack_frame(response, rx_bytes + PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN);")
    lines.append("    if(crc4_frame(response) != response->crc4) {")
    lines.append("        return PERIPHX_ERR_CRC;")
    lines.append("    }")
    lines.append("    if(response->server_id != request->server_id) {")
    lines.append("        return PERIPHX_ERR_RESPONSE;")
    lines.append("    }")
    lines.append("    return PERIPHX_OK;")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value)")
    lines.append("{")
    lines.append("    periphx_frame_t request = { service_id, value, PERIPHX_MSG_REQUEST, 0u };")
    lines.append("    periphx_frame_t response = {0};")
    lines.append("    int status = periphx_transfer_frame(dev, &request, &response);")
    lines.append("    if(status != PERIPHX_OK) {")
    lines.append("        return status;")
    lines.append("    }")
    lines.append("    if(response.msg_type == PERIPHX_MSG_ERROR) {")
    lines.append("        return PERIPHX_ERR_RESPONSE;")
    lines.append("    }")
    lines.append("    if(response.msg_type != PERIPHX_MSG_RESPONSE) {")
    lines.append("        return PERIPHX_ERR_RESPONSE;")
    lines.append("    }")
    lines.append("    if(response_value != NULL) {")
    lines.append("        *response_value = response.payload;")
    lines.append("    }")
    lines.append("    return PERIPHX_OK;")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value)")
    lines.append("{")
    lines.append("    return periphx_call_u32(dev, service_id, (uint32_t)value, response_value);")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value)")
    lines.append("{")
    lines.append("    return periphx_call_u32(dev, service_id, value ? 1u : 0u, response_value);")
    lines.append("}")
    lines.append("")
    if has_uart(spec):
        lines.extend(emit_uart_pack_config())
        lines.append("")
    for component in spec.components:
        if component.component_type == "uart":
            lines.extend(emit_uart_source_functions(spec, component))
        else:
            lines.extend(emit_generic_source_functions(component.services))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# @brief 将 PeriphX 服务数据类型转换为 C 语言类型名称。
# @param data_type manifest 或 interface 中声明的服务数据类型。
# @return 对应的 C 语言类型名称。
def c_type_name(data_type: str) -> str:
    if data_type == "bool":
        return "bool"
    if data_type == "u8":
        return "uint8_t"
    return "uint32_t"


# @brief 判断当前工程是否包含 uart 组件。
def has_uart(spec: ProjectSpec) -> bool:
    return any(component.component_type == "uart" for component in spec.components)


# @brief 输出 UART SDK 通用类型声明。
def emit_uart_type_declarations() -> list[str]:
    return [
        "typedef enum {",
        "    PERIPHX_UART_PARITY_NONE = 0,",
        "    PERIPHX_UART_PARITY_ODD = 1,",
        "    PERIPHX_UART_PARITY_EVEN = 2,",
        "} periphx_uart_parity_t;",
        "",
        "typedef struct {",
        "    uint32_t baudrate;",
        "    uint8_t data_bits;",
        "    periphx_uart_parity_t parity;",
        "    uint8_t stop_bits;",
        "} periphx_uart_config_t;",
        "",
        "#define PERIPHX_UART_STATUS_RX_EMPTY      (1u << 0)",
        "#define PERIPHX_UART_STATUS_RX_FULL       (1u << 1)",
        "#define PERIPHX_UART_STATUS_TX_EMPTY      (1u << 2)",
        "#define PERIPHX_UART_STATUS_TX_FULL       (1u << 3)",
        "#define PERIPHX_UART_STATUS_TX_BUSY       (1u << 4)",
        "#define PERIPHX_UART_STATUS_RX_OVERFLOW   (1u << 5)",
        "#define PERIPHX_UART_STATUS_PARITY_ERROR  (1u << 6)",
        "#define PERIPHX_UART_STATUS_FRAME_ERROR   (1u << 7)",
    ]


# @brief 输出非 UART 服务函数声明。
def emit_generic_header_functions(services: list[ServiceSpec]) -> list[str]:
    lines: list[str] = []
    for service in services:
        c_fn = service.c_function_name
        type_name = c_type_name(service.data_type)
        lines.append(
            f"int {c_fn}(periphx_device_t *dev, {type_name} value, uint32_t *response_value);"
        )
    return lines


# @brief 输出 UART 实例函数声明。
def emit_uart_header_functions(component: ComponentSpec) -> list[str]:
    prefix = sanitize_identifier(f"periphx_{component.name}")
    return [
        f"int {prefix}_configure(periphx_device_t *dev, const periphx_uart_config_t *config, uint32_t *response_value);",
        f"int {prefix}_write_byte(periphx_device_t *dev, uint8_t value, uint32_t *response_value);",
        f"int {prefix}_read_byte(periphx_device_t *dev, uint8_t *value);",
        f"int {prefix}_get_status(periphx_device_t *dev, uint32_t *status_value);",
        "",
    ]


# @brief 输出 UART 配置打包 helper。
def emit_uart_pack_config() -> list[str]:
    return [
        "static int periphx_pack_uart_config(uint32_t clock_hz, const periphx_uart_config_t *config, uint32_t *payload)",
        "{",
        "    uint32_t baud_div;",
        "",
        "    if(config == NULL || payload == NULL) {",
        "        return PERIPHX_ERR_PARAM;",
        "    }",
        "    if(clock_hz == 0u || config->baudrate == 0u) {",
        "        return PERIPHX_ERR_PARAM;",
        "    }",
        "    if(config->data_bits < 5u || config->data_bits > 8u) {",
        "        return PERIPHX_ERR_PARAM;",
        "    }",
        "    if(config->parity != PERIPHX_UART_PARITY_NONE &&",
        "       config->parity != PERIPHX_UART_PARITY_ODD &&",
        "       config->parity != PERIPHX_UART_PARITY_EVEN) {",
        "        return PERIPHX_ERR_PARAM;",
        "    }",
        "    if(config->stop_bits != 1u && config->stop_bits != 2u) {",
        "        return PERIPHX_ERR_PARAM;",
        "    }",
        "",
        "    baud_div = (clock_hz + (config->baudrate / 2u)) / config->baudrate;",
        "    if(baud_div == 0u || baud_div > 65535u) {",
        "        return PERIPHX_ERR_PARAM;",
        "    }",
        "",
        "    *payload = (baud_div & 0xFFFFu) |",
        "               (((uint32_t)(config->data_bits - 5u) & 0x7u) << 16) |",
        "               (((uint32_t)config->parity & 0x3u) << 19) |",
        "               (((uint32_t)(config->stop_bits - 1u) & 0x1u) << 21);",
        "    return PERIPHX_OK;",
        "}",
    ]


# @brief 输出非 UART 服务函数实现。
def emit_generic_source_functions(services: list[ServiceSpec]) -> list[str]:
    lines: list[str] = []
    for service in services:
        c_fn = service.c_function_name
        type_name = c_type_name(service.data_type)
        lines.append(
            f"int {c_fn}(periphx_device_t *dev, {type_name} value, uint32_t *response_value)"
        )
        lines.append("{")
        if service.data_type == "bool":
            lines.append(
                f"    return periphx_call_bool(dev, {service.c_macro_name}, value, response_value);"
            )
        elif service.data_type == "u8":
            lines.append(
                f"    return periphx_call_u8(dev, {service.c_macro_name}, value, response_value);"
            )
        else:
            lines.append(
                f"    return periphx_call_u32(dev, {service.c_macro_name}, value, response_value);"
            )
        lines.append("}")
        lines.append("")
    return lines


# @brief 输出 UART 实例函数实现。
def emit_uart_source_functions(spec: ProjectSpec, component: ComponentSpec) -> list[str]:
    prefix = sanitize_identifier(f"periphx_{component.name}")
    services = {service.name: service for service in component.services}
    missing = [name for name in UART_SERVICE_NAMES if name not in services]
    if missing:
        raise ValueError(
            f"uart component {component.name} missing services: {', '.join(missing)}"
        )

    clock_hz = sdk_clock_hz(spec)
    configure_macro = services["configure"].c_macro_name
    write_macro = services["write_byte"].c_macro_name
    read_macro = services["read_byte"].c_macro_name
    status_macro = services["get_status"].c_macro_name
    return [
        f"int {prefix}_configure(periphx_device_t *dev, const periphx_uart_config_t *config, uint32_t *response_value)",
        "{",
        "    uint32_t payload = 0u;",
        f"    int status = periphx_pack_uart_config({clock_hz}u, config, &payload);",
        "    if(status != PERIPHX_OK) {",
        "        return status;",
        "    }",
        f"    return periphx_call_u32(dev, {configure_macro}, payload, response_value);",
        "}",
        "",
        f"int {prefix}_write_byte(periphx_device_t *dev, uint8_t value, uint32_t *response_value)",
        "{",
        f"    return periphx_call_u8(dev, {write_macro}, value, response_value);",
        "}",
        "",
        f"int {prefix}_read_byte(periphx_device_t *dev, uint8_t *value)",
        "{",
        "    uint32_t response_value = 0u;",
        f"    int status = periphx_call_u32(dev, {read_macro}, 0u, &response_value);",
        "    if(status != PERIPHX_OK) {",
        "        return status;",
        "    }",
        "    if(value != NULL) {",
        "        *value = (uint8_t)(response_value & 0xFFu);",
        "    }",
        "    return PERIPHX_OK;",
        "}",
        "",
        f"int {prefix}_get_status(periphx_device_t *dev, uint32_t *status_value)",
        "{",
        f"    return periphx_call_u32(dev, {status_macro}, 0u, status_value);",
        "}",
        "",
    ]


# @brief 读取 SDK 生成需要使用的系统时钟频率。
def sdk_clock_hz(spec: ProjectSpec) -> int:
    clock_cfg = spec.config.get("clock", {}) or {}
    raw_freq = clock_cfg.get("input_freq", 50_000_000)
    if isinstance(raw_freq, str):
        raw_freq = raw_freq.replace("_", "")
    freq = int(raw_freq)
    if freq <= 0:
        raise ValueError("clock.input_freq must be positive for sdk")
    return freq
