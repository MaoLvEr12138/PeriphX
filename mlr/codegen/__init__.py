# @brief 代码生成包入口，集中导出兼容旧入口的生成接口和常量。
# @date 2026-07-28
# @author hzguo


from pathlib import Path
import json
from textwrap import dedent

from mlr.codegen.artifacts import generate_artifacts
from mlr.codegen.meta import write_service_map as _write_service_map
from mlr.codegen.meta import write_summary as _write_summary
from mlr.codegen.protocol import ERROR_MSG_TYPE
from mlr.codegen.protocol import EVENT_MSG_TYPE
from mlr.codegen.protocol import FRAME_LEN
from mlr.codegen.protocol import REQUEST_MSG_TYPE
from mlr.codegen.protocol import RESPONSE_MSG_TYPE
from mlr.codegen.protocol import TURNAROUND_BYTE
from mlr.codegen.protocol import TURNAROUND_LEN
from mlr.codegen.rtl.components.pwm_led import emit_pwm_led_adapter as _emit_pwm_led_adapter
from mlr.codegen.rtl.components.pwm_led import emit_pwm_led_instance as _emit_pwm_led_instance
from mlr.codegen.rtl.components.uart import emit_uart_adapter as _emit_uart_adapter
from mlr.codegen.rtl.components.uart import emit_uart_instance as _emit_uart_instance
from mlr.codegen.rtl.components.uart import is_uart_output_pin as _is_uart_output_pin
from mlr.codegen.rtl.top import emit_top_module as _emit_top_module
from mlr.codegen.rtl.top import is_output_pin as _is_output_pin
from mlr.codegen.rtl.top import write_generated_rtl as _write_generated_rtl
from mlr.codegen.sdk import c_type_name as _c_type_name
from mlr.codegen.sdk import write_sdk_header as _write_sdk_header
from mlr.codegen.sdk import write_sdk_source as _write_sdk_source
from mlr.project import ComponentSpec, ProjectSpec, sanitize_identifier
