# @brief SDK 生成模块，负责输出 PeriphX C 语言 SDK 头文件和源文件。
# @date 2026-07-28
# @author hzguo


from __future__ import annotations

from pathlib import Path

from mlr.codegen.protocol import (
    ERR_BUSY,
    ERROR_MSG_TYPE,
    EVENT_MSG_TYPE,
    FRAME_LEN,
    POLL_MSG_TYPE,
    REQUEST_MSG_TYPE,
    RESPONSE_MSG_TYPE,
    TURNAROUND_BYTE,
    TURNAROUND_LEN,
)
from mlr.project import ComponentSpec, ProjectSpec, ServiceSpec, sanitize_identifier

UART_SERVICE_NAMES = ["configure", "write_byte", "read_byte", "get_status"]
I2C_SERVICE_NAMES = [
    "set_clk_div",
    "set_stretch_timeout",
    "set_dev_addr",
    "set_reg_addr",
    "set_length",
    "push_write_data",
    "start_write",
    "start_read",
    "pop_read_data",
    "get_status",
    "clear_status",
]


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
    lines.append("#define PERIPHX_EXCHANGE_LEN (PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN)")
    lines.append("#define PERIPHX_DEFAULT_MAX_POLLS 16u")
    lines.append(f"#define PERIPHX_MSG_REQUEST {REQUEST_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_RESPONSE {RESPONSE_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_EVENT {EVENT_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_ERROR {ERROR_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_POLL {POLL_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_BUSY_PAYLOAD 0x{ERR_BUSY:08X}u")
    lines.append("")
    lines.append("typedef enum {")
    lines.append("    PERIPHX_OK = 0,")
    lines.append("    PERIPHX_ERR_IO = -1,")
    lines.append("    PERIPHX_ERR_FRAME = -2,")
    lines.append("    PERIPHX_ERR_CRC = -3,")
    lines.append("    PERIPHX_ERR_RESPONSE = -4,")
    lines.append("    PERIPHX_ERR_PARAM = -5,")
    lines.append("    PERIPHX_ERR_BUSY = -6,")
    lines.append("    PERIPHX_ERR_TIMEOUT = -7,")
    lines.append("} periphx_status_t;")
    lines.append("")
    lines.append(
        "typedef int (*periphx_transport_fn)(void *user, const uint8_t *tx, uint8_t *rx, size_t len);"
    )
    lines.append("typedef uint32_t (*periphx_time_ms_fn)(void *user);")
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    periphx_transport_fn transfer;")
    lines.append("    void *user;")
    lines.append("    periphx_time_ms_fn time_ms;")
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
    if has_i2c(spec):
        lines.extend(emit_i2c_type_declarations())
        lines.append("")
    for service in spec.services:
        macro = service.c_macro_name
        lines.append(f"#define {macro} {service.service_id}u")
    lines.append("")
    lines.append("void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user);")
    lines.append("void periphx_device_set_time_ms(periphx_device_t *dev, periphx_time_ms_fn time_ms);")
    lines.append(
        "int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response);"
    )
    lines.append(
        "int periphx_transfer_frame_poll(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response, uint32_t max_polls);"
    )
    lines.append(
        "int periphx_transfer_frame_timeout_ms(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response, uint32_t timeout_ms);"
    )
    lines.append("int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value);")
    lines.append("int periphx_call_u32_poll(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t max_polls, uint32_t *response_value);")
    lines.append("int periphx_call_u32_timeout_ms(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t timeout_ms, uint32_t *response_value);")
    lines.append("int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value);")
    lines.append("int periphx_call_u8_poll(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t max_polls, uint32_t *response_value);")
    lines.append("int periphx_call_u8_timeout_ms(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t timeout_ms, uint32_t *response_value);")
    lines.append("int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value);")
    lines.append("int periphx_call_bool_poll(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t max_polls, uint32_t *response_value);")
    lines.append("int periphx_call_bool_timeout_ms(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t timeout_ms, uint32_t *response_value);")
    lines.append("")
    for component in spec.components:
        if component.component_type == "uart":
            lines.extend(emit_uart_header_functions(component))
        elif component.component_type == "i2c":
            lines.extend(emit_generic_header_functions(component.services))
            lines.extend(emit_i2c_header_functions(component))
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
    lines.extend(emit_protocol_source())
    lines.append("")
    if has_uart(spec):
        lines.extend(emit_uart_pack_config())
        lines.append("")
    if has_i2c(spec):
        lines.extend(emit_i2c_common_source())
        lines.append("")
    for component in spec.components:
        if component.component_type == "uart":
            lines.extend(emit_uart_source_functions(spec, component))
        elif component.component_type == "i2c":
            lines.extend(emit_generic_source_functions(component.services))
            lines.extend(emit_i2c_source_functions(component))
        else:
            lines.extend(emit_generic_source_functions(component.services))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# @brief 输出协议、CRC 和通用调用 helper。
def emit_protocol_source() -> list[str]:
    return [
        "static uint8_t crc4_step(uint8_t crc_in, uint8_t bit_in)",
        "{",
        "    uint8_t feedback = (uint8_t)(((crc_in >> 3) ^ bit_in) & 0x1u);",
        "    uint8_t crc_out = (uint8_t)((crc_in << 1) & 0xFu);",
        "    if(feedback) {",
        "        crc_out ^= 0x3u;",
        "    }",
        "    return (uint8_t)(crc_out & 0xFu);",
        "}",
        "",
        "static uint8_t crc4_byte(uint8_t crc_in, uint8_t data)",
        "{",
        "    for(int bit = 7; bit >= 0; --bit) {",
        "        uint8_t bit_value = (uint8_t)((data >> bit) & 0x1u);",
        "        crc_in = crc4_step(crc_in, bit_value);",
        "    }",
        "    return (uint8_t)(crc_in & 0xFu);",
        "}",
        "",
        "static uint8_t crc4_nibble(uint8_t crc_in, uint8_t data)",
        "{",
        "    for(int bit = 3; bit >= 0; --bit) {",
        "        uint8_t bit_value = (uint8_t)((data >> bit) & 0x1u);",
        "        crc_in = crc4_step(crc_in, bit_value);",
        "    }",
        "    return (uint8_t)(crc_in & 0xFu);",
        "}",
        "",
        "static uint8_t crc4_frame(const periphx_frame_t *frame)",
        "{",
        "    uint8_t crc = 0u;",
        "    crc = crc4_byte(crc, frame->server_id);",
        "    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 24));",
        "    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 16));",
        "    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 8));",
        "    crc = crc4_byte(crc, (uint8_t)frame->payload);",
        "    crc = crc4_nibble(crc, frame->msg_type);",
        "    return (uint8_t)(crc & 0xFu);",
        "}",
        "",
        "static void pack_frame(const periphx_frame_t *frame, uint8_t bytes[PERIPHX_FRAME_LEN])",
        "{",
        "    bytes[0] = frame->server_id;",
        "    bytes[1] = (uint8_t)(frame->payload >> 24);",
        "    bytes[2] = (uint8_t)(frame->payload >> 16);",
        "    bytes[3] = (uint8_t)(frame->payload >> 8);",
        "    bytes[4] = (uint8_t)frame->payload;",
        "    bytes[5] = (uint8_t)(((frame->crc4 & 0xFu) << 4) | (frame->msg_type & 0xFu));",
        "}",
        "",
        "static void unpack_frame(periphx_frame_t *frame, const uint8_t bytes[PERIPHX_FRAME_LEN])",
        "{",
        "    frame->server_id = bytes[0];",
        "    frame->payload = ((uint32_t)bytes[1] << 24) | ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 8) | (uint32_t)bytes[4];",
        "    frame->msg_type = (uint8_t)(bytes[5] & 0xFu);",
        "    frame->crc4 = (uint8_t)((bytes[5] >> 4) & 0xFu);",
        "}",
        "",
        "void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user)",
        "{",
        "    if(dev != NULL) {",
        "        dev->transfer = transfer;",
        "        dev->user = user;",
        "        dev->time_ms = NULL;",
        "    }",
        "}",
        "",
        "void periphx_device_set_time_ms(periphx_device_t *dev, periphx_time_ms_fn time_ms)",
        "{",
        "    if(dev != NULL) {",
        "        dev->time_ms = time_ms;",
        "    }",
        "}",
        "",
        "static int transfer_bytes(periphx_device_t *dev, const uint8_t *tx_bytes, uint8_t *rx_bytes, size_t len)",
        "{",
        "    int status = PERIPHX_OK;",
        "    if((dev == NULL) || (tx_bytes == NULL) || (rx_bytes == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else if(dev->transfer == NULL) {",
        "        status = PERIPHX_ERR_IO;",
        "    } else if(dev->transfer(dev->user, tx_bytes, rx_bytes, len) != 0) {",
        "        status = PERIPHX_ERR_IO;",
        "    } else {",
        "        status = PERIPHX_OK;",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_exchange_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response)",
        "{",
        "    uint8_t tx_bytes[PERIPHX_EXCHANGE_LEN];",
        "    uint8_t rx_bytes[PERIPHX_EXCHANGE_LEN];",
        "    int status = PERIPHX_OK;",
        "",
        "    if((request == NULL) || (response == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else {",
        "        periphx_frame_t tmp = *request;",
        "        tmp.msg_type &= 0xFu;",
        "        tmp.crc4 = crc4_frame(&tmp);",
        "        pack_frame(&tmp, tx_bytes);",
        "        for(size_t i = 0u; i < (PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN); ++i) {",
        f"            tx_bytes[PERIPHX_FRAME_LEN + i] = 0x{TURNAROUND_BYTE:02X}u;",
        "        }",
        "        status = transfer_bytes(dev, tx_bytes, rx_bytes, PERIPHX_EXCHANGE_LEN);",
        "        if(status == PERIPHX_OK) {",
        "            const uint8_t *readback = &rx_bytes[PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN];",
        "            unpack_frame(response, readback);",
        "            if(crc4_frame(response) != response->crc4) {",
        "                status = PERIPHX_ERR_CRC;",
        "            } else if(response->server_id != request->server_id) {",
        "                status = PERIPHX_ERR_RESPONSE;",
        "            } else {",
        "                status = PERIPHX_OK;",
        "            }",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_status_from_error_payload(uint32_t payload)",
        "{",
        "    int status = PERIPHX_ERR_RESPONSE;",
        "    if(payload == PERIPHX_BUSY_PAYLOAD) {",
        "        status = PERIPHX_ERR_BUSY;",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_submit_request(periphx_device_t *dev, const periphx_frame_t *request)",
        "{",
        "    periphx_frame_t ack = {0u, 0u, 0u, 0u};",
        "    int status = periphx_exchange_frame(dev, request, &ack);",
        "    if(status == PERIPHX_OK) {",
        "        if(ack.msg_type == PERIPHX_MSG_ERROR) {",
        "            status = periphx_status_from_error_payload(ack.payload);",
        "        } else if((ack.msg_type != PERIPHX_MSG_RESPONSE) || (ack.payload != 0u)) {",
        "            status = PERIPHX_ERR_RESPONSE;",
        "        } else {",
        "            status = PERIPHX_OK;",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_poll_response_once(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response)",
        "{",
        "    periphx_frame_t poll = {0u, 0u, PERIPHX_MSG_POLL, 0u};",
        "    int status = PERIPHX_OK;",
        "    if((request == NULL) || (response == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else {",
        "        poll.server_id = request->server_id;",
        "        status = periphx_exchange_frame(dev, &poll, response);",
        "        if(status == PERIPHX_OK) {",
        "            if(response->msg_type == PERIPHX_MSG_ERROR) {",
        "                status = periphx_status_from_error_payload(response->payload);",
        "            } else if(response->msg_type != PERIPHX_MSG_RESPONSE) {",
        "                status = PERIPHX_ERR_RESPONSE;",
        "            } else {",
        "                status = PERIPHX_OK;",
        "            }",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "int periphx_transfer_frame_poll(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response, uint32_t max_polls)",
        "{",
        "    int status = periphx_submit_request(dev, request);",
        "    uint32_t poll_count = 0u;",
        "    bool response_done = false;",
        "",
        "    while((status == PERIPHX_OK) && !response_done && (poll_count < max_polls)) {",
        "        status = periphx_poll_response_once(dev, request, response);",
        "        if(status == PERIPHX_ERR_BUSY) {",
        "            poll_count++;",
        "            status = PERIPHX_OK;",
        "        } else {",
        "            response_done = true;",
        "        }",
        "    }",
        "    if((status == PERIPHX_OK) && !response_done) {",
        "        status = PERIPHX_ERR_TIMEOUT;",
        "    }",
        "    return status;",
        "}",
        "",
        "int periphx_transfer_frame_timeout_ms(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response, uint32_t timeout_ms)",
        "{",
        "    int status = PERIPHX_OK;",
        "    bool response_done = false;",
        "    uint32_t start_ms = 0u;",
        "",
        "    if((dev == NULL) || (dev->time_ms == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else {",
        "        start_ms = dev->time_ms(dev->user);",
        "        status = periphx_submit_request(dev, request);",
        "    }",
        "",
        "    while((status == PERIPHX_OK) && !response_done) {",
        "        status = periphx_poll_response_once(dev, request, response);",
        "        if(status == PERIPHX_ERR_BUSY) {",
        "            uint32_t now_ms = dev->time_ms(dev->user);",
        "            uint32_t elapsed_ms = (uint32_t)(now_ms - start_ms);",
        "            if(elapsed_ms >= timeout_ms) {",
        "                status = PERIPHX_ERR_TIMEOUT;",
        "            } else {",
        "                status = PERIPHX_OK;",
        "            }",
        "        } else {",
        "            response_done = true;",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response)",
        "{",
        "    return periphx_transfer_frame_poll(dev, request, response, PERIPHX_DEFAULT_MAX_POLLS);",
        "}",
        "",
        "int periphx_call_u32_poll(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t max_polls, uint32_t *response_value)",
        "{",
        "    periphx_frame_t request = { service_id, value, PERIPHX_MSG_REQUEST, 0u };",
        "    periphx_frame_t response = {0u, 0u, 0u, 0u};",
        "    int status = periphx_transfer_frame_poll(dev, &request, &response, max_polls);",
        "    if(status == PERIPHX_OK) {",
        "        if(response_value != NULL) {",
        "            *response_value = response.payload;",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "int periphx_call_u32_timeout_ms(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t timeout_ms, uint32_t *response_value)",
        "{",
        "    periphx_frame_t request = { service_id, value, PERIPHX_MSG_REQUEST, 0u };",
        "    periphx_frame_t response = {0u, 0u, 0u, 0u};",
        "    int status = periphx_transfer_frame_timeout_ms(dev, &request, &response, timeout_ms);",
        "    if(status == PERIPHX_OK) {",
        "        if(response_value != NULL) {",
        "            *response_value = response.payload;",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value)",
        "{",
        "    return periphx_call_u32_poll(dev, service_id, value, PERIPHX_DEFAULT_MAX_POLLS, response_value);",
        "}",
        "",
        "int periphx_call_u8_poll(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t max_polls, uint32_t *response_value)",
        "{",
        "    return periphx_call_u32_poll(dev, service_id, (uint32_t)value, max_polls, response_value);",
        "}",
        "",
        "int periphx_call_u8_timeout_ms(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t timeout_ms, uint32_t *response_value)",
        "{",
        "    return periphx_call_u32_timeout_ms(dev, service_id, (uint32_t)value, timeout_ms, response_value);",
        "}",
        "",
        "int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value)",
        "{",
        "    return periphx_call_u8_poll(dev, service_id, value, PERIPHX_DEFAULT_MAX_POLLS, response_value);",
        "}",
        "",
        "int periphx_call_bool_poll(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t max_polls, uint32_t *response_value)",
        "{",
        "    uint32_t payload = value ? 1u : 0u;",
        "    return periphx_call_u32_poll(dev, service_id, payload, max_polls, response_value);",
        "}",
        "",
        "int periphx_call_bool_timeout_ms(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t timeout_ms, uint32_t *response_value)",
        "{",
        "    uint32_t payload = value ? 1u : 0u;",
        "    return periphx_call_u32_timeout_ms(dev, service_id, payload, timeout_ms, response_value);",
        "}",
        "",
        "int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value)",
        "{",
        "    return periphx_call_bool_poll(dev, service_id, value, PERIPHX_DEFAULT_MAX_POLLS, response_value);",
        "}",
    ]


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


# @brief 判断当前工程是否包含 i2c 组件。
def has_i2c(spec: ProjectSpec) -> bool:
    return any(component.component_type == "i2c" for component in spec.components)


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


# @brief 输出 I2C SDK 通用类型声明。
def emit_i2c_type_declarations() -> list[str]:
    return [
        "#define PERIPHX_I2C_STATUS_BUSY            (1u << 0)",
        "#define PERIPHX_I2C_STATUS_DONE            (1u << 1)",
        "#define PERIPHX_I2C_STATUS_ACK_ERROR       (1u << 2)",
        "#define PERIPHX_I2C_STATUS_STRETCH_TIMEOUT (1u << 3)",
        "#define PERIPHX_I2C_STATUS_ARB_LOST        (1u << 4)",
        "#define PERIPHX_I2C_STATUS_TX_FULL         (1u << 5)",
        "#define PERIPHX_I2C_STATUS_TX_EMPTY        (1u << 6)",
        "#define PERIPHX_I2C_STATUS_RX_FULL         (1u << 7)",
        "#define PERIPHX_I2C_STATUS_RX_EMPTY        (1u << 8)",
        "#define PERIPHX_I2C_STATUS_ERROR_MASK      0x0000F000u",
        "#define PERIPHX_I2C_STATUS_ERROR_SHIFT     12u",
        "#define PERIPHX_I2C_STATUS_TX_COUNT_SHIFT  16u",
        "#define PERIPHX_I2C_STATUS_RX_COUNT_SHIFT  24u",
        "",
        "#define PERIPHX_I2C_CLEAR_DONE             (1u << 1)",
        "#define PERIPHX_I2C_CLEAR_ACK_ERROR        (1u << 2)",
        "#define PERIPHX_I2C_CLEAR_STRETCH_TIMEOUT  (1u << 3)",
        "#define PERIPHX_I2C_CLEAR_ARB_LOST         (1u << 4)",
        "#define PERIPHX_I2C_CLEAR_TX               (1u << 8)",
        "#define PERIPHX_I2C_CLEAR_RX               (1u << 9)",
        "#define PERIPHX_I2C_CLEAR_ERROR_CODE       (1u << 15)",
        "",
        "#define PERIPHX_I2C_ERR_NONE               0u",
        "#define PERIPHX_I2C_ERR_ADDR_WRITE_NACK    1u",
        "#define PERIPHX_I2C_ERR_REG_ADDR_NACK      2u",
        "#define PERIPHX_I2C_ERR_WRITE_DATA_NACK    3u",
        "#define PERIPHX_I2C_ERR_ADDR_READ_NACK     4u",
        "#define PERIPHX_I2C_ERR_STRETCH_TIMEOUT    5u",
        "#define PERIPHX_I2C_ERR_ARB_LOST           6u",
        "#define PERIPHX_I2C_ERR_INVALID_LENGTH     7u",
        "#define PERIPHX_I2C_ERR_TX_UNDERFLOW       8u",
        "#define PERIPHX_I2C_ERR_RX_OVERFLOW        9u",
        "",
        "#define PERIPHX_I2C_RESP_OK                0u",
        "#define PERIPHX_I2C_RESP_BUSY              1u",
        "#define PERIPHX_I2C_RESP_INVALID           2u",
        "#define PERIPHX_I2C_RESP_FULL              3u",
        "#define PERIPHX_I2C_RESP_EMPTY             4u",
        "",
        "#define PERIPHX_I2C_NO_REG_ADDR             0xFFu",
        "",
        "typedef struct {",
        "    uint32_t clk_div;",
        "    uint32_t stretch_timeout;",
        "} periphx_i2c_config_t;",
        "",
        "typedef struct {",
        "    uint8_t dev_addr;",
        "    uint8_t reg_addr;",
        "    uint8_t length;",
        "    const uint8_t *write_data;",
        "    uint8_t *read_data;",
        "} periphx_i2c_transfer_t;",
    ]


# @brief 输出非 UART/I2C 高层服务函数声明。
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


# @brief 输出 I2C 实例高层函数声明。
def emit_i2c_header_functions(component: ComponentSpec) -> list[str]:
    prefix = sanitize_identifier(f"periphx_{component.name}")
    return [
        f"int {prefix}_i2c_configure_poll(periphx_device_t *dev, const periphx_i2c_config_t *config, uint32_t max_polls);",
        f"int {prefix}_i2c_configure_timeout_ms(periphx_device_t *dev, const periphx_i2c_config_t *config, uint32_t timeout_ms);",
        f"int {prefix}_i2c_configure(periphx_device_t *dev, const periphx_i2c_config_t *config);",
        f"int {prefix}_i2c_write_poll(periphx_device_t *dev, const periphx_i2c_transfer_t *transfer, uint32_t max_polls);",
        f"int {prefix}_i2c_write_timeout_ms(periphx_device_t *dev, const periphx_i2c_transfer_t *transfer, uint32_t timeout_ms);",
        f"int {prefix}_i2c_write(periphx_device_t *dev, const periphx_i2c_transfer_t *transfer);",
        f"int {prefix}_i2c_read_poll(periphx_device_t *dev, periphx_i2c_transfer_t *transfer, uint32_t max_polls);",
        f"int {prefix}_i2c_read_timeout_ms(periphx_device_t *dev, periphx_i2c_transfer_t *transfer, uint32_t timeout_ms);",
        f"int {prefix}_i2c_read(periphx_device_t *dev, periphx_i2c_transfer_t *transfer);",
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


# @brief 输出 I2C 高层 helper 共用实现。
def emit_i2c_common_source() -> list[str]:
    return [
        "typedef struct {",
        "    uint8_t set_clk_div_id;",
        "    uint8_t set_stretch_timeout_id;",
        "    uint8_t set_dev_addr_id;",
        "    uint8_t set_reg_addr_id;",
        "    uint8_t set_length_id;",
        "    uint8_t push_write_data_id;",
        "    uint8_t start_write_id;",
        "    uint8_t start_read_id;",
        "    uint8_t pop_read_data_id;",
        "    uint8_t get_status_id;",
        "    uint8_t clear_status_id;",
        "} periphx_i2c_service_ids_t;",
        "",
        "static int periphx_i2c_check_response(uint32_t response_value)",
        "{",
        "    int status;",
        "    switch(response_value) {",
        "    case PERIPHX_I2C_RESP_OK:",
        "        status = PERIPHX_OK;",
        "        break;",
        "    case PERIPHX_I2C_RESP_BUSY:",
        "        status = PERIPHX_ERR_BUSY;",
        "        break;",
        "    case PERIPHX_I2C_RESP_INVALID:",
        "        status = PERIPHX_ERR_PARAM;",
        "        break;",
        "    case PERIPHX_I2C_RESP_FULL:",
        "    case PERIPHX_I2C_RESP_EMPTY:",
        "    default:",
        "        status = PERIPHX_ERR_RESPONSE;",
        "        break;",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_i2c_expect_echo(uint32_t response_value, uint32_t expected_value)",
        "{",
        "    int status = PERIPHX_OK;",
        "    if(response_value != expected_value) {",
        "        status = periphx_i2c_check_response(response_value);",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_i2c_call_u32_wait(periphx_device_t *dev, uint8_t service_id, uint32_t value, bool use_timeout, uint32_t wait_value, uint32_t *response_value)",
        "{",
        "    int status;",
        "    if(use_timeout) {",
        "        status = periphx_call_u32_timeout_ms(dev, service_id, value, wait_value, response_value);",
        "    } else {",
        "        status = periphx_call_u32_poll(dev, service_id, value, wait_value, response_value);",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_i2c_wait_done_common(periphx_device_t *dev, const periphx_i2c_service_ids_t *ids, bool use_timeout, uint32_t wait_value)",
        "{",
        "    int status = PERIPHX_OK;",
        "    bool done = false;",
        "    uint32_t poll_count = 0u;",
        "    uint32_t start_ms = 0u;",
        "",
        "    if(ids == NULL) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else if(use_timeout && ((dev == NULL) || (dev->time_ms == NULL))) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else {",
        "        if(use_timeout) {",
        "            start_ms = dev->time_ms(dev->user);",
        "        }",
        "    }",
        "",
        "    while((status == PERIPHX_OK) && !done) {",
        "        uint32_t status_value = 0u;",
        "        status = periphx_i2c_call_u32_wait(dev, ids->get_status_id, 0u, use_timeout, wait_value, &status_value);",
        "        if(status == PERIPHX_OK) {",
        "            uint32_t error_bits = status_value & (PERIPHX_I2C_STATUS_ACK_ERROR | PERIPHX_I2C_STATUS_STRETCH_TIMEOUT | PERIPHX_I2C_STATUS_ARB_LOST);",
        "            uint32_t error_code = (status_value & PERIPHX_I2C_STATUS_ERROR_MASK) >> PERIPHX_I2C_STATUS_ERROR_SHIFT;",
        "            bool is_busy = (status_value & PERIPHX_I2C_STATUS_BUSY) != 0u;",
        "            bool is_done = (status_value & PERIPHX_I2C_STATUS_DONE) != 0u;",
        "            if((error_bits != 0u) || (error_code != PERIPHX_I2C_ERR_NONE)) {",
        "                status = PERIPHX_ERR_RESPONSE;",
        "            } else if(!is_busy && is_done) {",
        "                done = true;",
        "            } else if(use_timeout) {",
        "                uint32_t now_ms = dev->time_ms(dev->user);",
        "                uint32_t elapsed_ms = (uint32_t)(now_ms - start_ms);",
        "                if(elapsed_ms >= wait_value) {",
        "                    status = PERIPHX_ERR_TIMEOUT;",
        "                }",
        "            } else {",
        "                poll_count++;",
        "                if(poll_count >= wait_value) {",
        "                    status = PERIPHX_ERR_TIMEOUT;",
        "                }",
        "            }",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_i2c_configure_common(periphx_device_t *dev, const periphx_i2c_service_ids_t *ids, const periphx_i2c_config_t *config, bool use_timeout, uint32_t wait_value)",
        "{",
        "    int status = PERIPHX_OK;",
        "    uint32_t response_value = 0u;",
        "    if((ids == NULL) || (config == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    }",
        "    if(status == PERIPHX_OK) {",
        "        status = periphx_i2c_call_u32_wait(dev, ids->set_clk_div_id, config->clk_div, use_timeout, wait_value, &response_value);",
        "        if(status == PERIPHX_OK) {",
        "            status = periphx_i2c_expect_echo(response_value, config->clk_div);",
        "        }",
        "    }",
        "    if(status == PERIPHX_OK) {",
        "        status = periphx_i2c_call_u32_wait(dev, ids->set_stretch_timeout_id, config->stretch_timeout, use_timeout, wait_value, &response_value);",
        "        if(status == PERIPHX_OK) {",
        "            status = periphx_i2c_expect_echo(response_value, config->stretch_timeout);",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        "static int periphx_i2c_transfer_common(periphx_device_t *dev, const periphx_i2c_service_ids_t *ids, periphx_i2c_transfer_t *transfer, bool read_transfer, bool use_timeout, uint32_t wait_value)",
        "{",
        "    int status = PERIPHX_OK;",
        "    uint32_t response_value = 0u;",
        "",
        "    if((ids == NULL) || (transfer == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else if((transfer->length == 0u) || (transfer->length > 16u)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else if(read_transfer && (transfer->read_data == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else if(!read_transfer && (transfer->write_data == NULL)) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else {",
        "        status = PERIPHX_OK;",
        "    }",
        "",
        "    if(status == PERIPHX_OK) {",
        "        uint32_t expected_dev_addr = (uint32_t)(transfer->dev_addr & 0x7Fu);",
        "        status = periphx_i2c_call_u32_wait(dev, ids->set_dev_addr_id, transfer->dev_addr, use_timeout, wait_value, &response_value);",
        "        if(status == PERIPHX_OK) {",
        "            status = periphx_i2c_expect_echo(response_value, expected_dev_addr);",
        "        }",
        "    }",
        "    if(status == PERIPHX_OK) {",
        "        status = periphx_i2c_call_u32_wait(dev, ids->set_reg_addr_id, transfer->reg_addr, use_timeout, wait_value, &response_value);",
        "        if(status == PERIPHX_OK) {",
        "            status = periphx_i2c_expect_echo(response_value, (uint32_t)transfer->reg_addr);",
        "        }",
        "    }",
        "    if(status == PERIPHX_OK) {",
        "        status = periphx_i2c_call_u32_wait(dev, ids->set_length_id, transfer->length, use_timeout, wait_value, &response_value);",
        "        if(status == PERIPHX_OK) {",
        "            status = periphx_i2c_check_response(response_value);",
        "        }",
        "    }",
        "    if((status == PERIPHX_OK) && !read_transfer) {",
        "        for(uint8_t index = 0u; (index < transfer->length) && (status == PERIPHX_OK); ++index) {",
        "            uint8_t write_value = transfer->write_data[index];",
        "            status = periphx_i2c_call_u32_wait(dev, ids->push_write_data_id, write_value, use_timeout, wait_value, &response_value);",
        "            if(status == PERIPHX_OK) {",
        "                status = periphx_i2c_check_response(response_value);",
        "            }",
        "        }",
        "    }",
        "    if(status == PERIPHX_OK) {",
        "        uint8_t start_id = read_transfer ? ids->start_read_id : ids->start_write_id;",
        "        status = periphx_i2c_call_u32_wait(dev, start_id, 1u, use_timeout, wait_value, &response_value);",
        "        if(status == PERIPHX_OK) {",
        "            status = periphx_i2c_check_response(response_value);",
        "        }",
        "    }",
        "    if(status == PERIPHX_OK) {",
        "        status = periphx_i2c_wait_done_common(dev, ids, use_timeout, wait_value);",
        "    }",
        "    if((status == PERIPHX_OK) && read_transfer) {",
        "        for(uint8_t index = 0u; (index < transfer->length) && (status == PERIPHX_OK); ++index) {",
        "            status = periphx_i2c_call_u32_wait(dev, ids->pop_read_data_id, 0u, use_timeout, wait_value, &response_value);",
        "            if(status == PERIPHX_OK) {",
        "                transfer->read_data[index] = (uint8_t)(response_value & 0xFFu);",
        "            }",
        "        }",
        "    }",
        "    return status;",
        "}",
    ]


# @brief 输出非专用服务函数实现。
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
        "    if(status == PERIPHX_OK) {",
        f"        status = periphx_call_u32(dev, {configure_macro}, payload, response_value);",
        "    }",
        "    return status;",
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
        "    if(status == PERIPHX_OK) {",
        "        if(value != NULL) {",
        "            *value = (uint8_t)(response_value & 0xFFu);",
        "        }",
        "    }",
        "    return status;",
        "}",
        "",
        f"int {prefix}_get_status(periphx_device_t *dev, uint32_t *status_value)",
        "{",
        f"    return periphx_call_u32(dev, {status_macro}, 0u, status_value);",
        "}",
        "",
    ]


# @brief 输出 I2C 实例高层函数实现。
def emit_i2c_source_functions(component: ComponentSpec) -> list[str]:
    prefix = sanitize_identifier(f"periphx_{component.name}")
    services = {service.name: service for service in component.services}
    missing = [name for name in I2C_SERVICE_NAMES if name not in services]
    if missing:
        raise ValueError(
            f"i2c component {component.name} missing services: {', '.join(missing)}"
        )

    ids_name = f"{prefix}_i2c_ids"
    id_lines = [
        f"static const periphx_i2c_service_ids_t {ids_name} = {{",
        f"    {services['set_clk_div'].c_macro_name},",
        f"    {services['set_stretch_timeout'].c_macro_name},",
        f"    {services['set_dev_addr'].c_macro_name},",
        f"    {services['set_reg_addr'].c_macro_name},",
        f"    {services['set_length'].c_macro_name},",
        f"    {services['push_write_data'].c_macro_name},",
        f"    {services['start_write'].c_macro_name},",
        f"    {services['start_read'].c_macro_name},",
        f"    {services['pop_read_data'].c_macro_name},",
        f"    {services['get_status'].c_macro_name},",
        f"    {services['clear_status'].c_macro_name}",
        "};",
        "",
    ]
    func_lines = [
        f"int {prefix}_i2c_configure_poll(periphx_device_t *dev, const periphx_i2c_config_t *config, uint32_t max_polls)",
        "{",
        f"    return periphx_i2c_configure_common(dev, &{ids_name}, config, false, max_polls);",
        "}",
        "",
        f"int {prefix}_i2c_configure_timeout_ms(periphx_device_t *dev, const periphx_i2c_config_t *config, uint32_t timeout_ms)",
        "{",
        f"    return periphx_i2c_configure_common(dev, &{ids_name}, config, true, timeout_ms);",
        "}",
        "",
        f"int {prefix}_i2c_configure(periphx_device_t *dev, const periphx_i2c_config_t *config)",
        "{",
        f"    return {prefix}_i2c_configure_poll(dev, config, PERIPHX_DEFAULT_MAX_POLLS);",
        "}",
        "",
        f"int {prefix}_i2c_write_poll(periphx_device_t *dev, const periphx_i2c_transfer_t *transfer, uint32_t max_polls)",
        "{",
        "    periphx_i2c_transfer_t local_transfer;",
        "    int status = PERIPHX_OK;",
        "    if(transfer == NULL) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else {",
        "        local_transfer = *transfer;",
        f"        status = periphx_i2c_transfer_common(dev, &{ids_name}, &local_transfer, false, false, max_polls);",
        "    }",
        "    return status;",
        "}",
        "",
        f"int {prefix}_i2c_write_timeout_ms(periphx_device_t *dev, const periphx_i2c_transfer_t *transfer, uint32_t timeout_ms)",
        "{",
        "    periphx_i2c_transfer_t local_transfer;",
        "    int status = PERIPHX_OK;",
        "    if(transfer == NULL) {",
        "        status = PERIPHX_ERR_PARAM;",
        "    } else {",
        "        local_transfer = *transfer;",
        f"        status = periphx_i2c_transfer_common(dev, &{ids_name}, &local_transfer, false, true, timeout_ms);",
        "    }",
        "    return status;",
        "}",
        "",
        f"int {prefix}_i2c_write(periphx_device_t *dev, const periphx_i2c_transfer_t *transfer)",
        "{",
        f"    return {prefix}_i2c_write_poll(dev, transfer, PERIPHX_DEFAULT_MAX_POLLS);",
        "}",
        "",
        f"int {prefix}_i2c_read_poll(periphx_device_t *dev, periphx_i2c_transfer_t *transfer, uint32_t max_polls)",
        "{",
        f"    return periphx_i2c_transfer_common(dev, &{ids_name}, transfer, true, false, max_polls);",
        "}",
        "",
        f"int {prefix}_i2c_read_timeout_ms(periphx_device_t *dev, periphx_i2c_transfer_t *transfer, uint32_t timeout_ms)",
        "{",
        f"    return periphx_i2c_transfer_common(dev, &{ids_name}, transfer, true, true, timeout_ms);",
        "}",
        "",
        f"int {prefix}_i2c_read(periphx_device_t *dev, periphx_i2c_transfer_t *transfer)",
        "{",
        f"    return {prefix}_i2c_read_poll(dev, transfer, PERIPHX_DEFAULT_MAX_POLLS);",
        "}",
        "",
    ]
    return id_lines + func_lines


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
