from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mlr.codegen.artifacts import generate_artifacts
from mlr.project import load_project_spec


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPO_ROOT / "userSpace"


def make_uart_manifest() -> dict:
    return {
        "manifest_version": 1.0,
        "config": {
            "fpga": {
                "brand": "Altera",
                "family": "Cyclone IV E",
                "device": "EP4CE6E22C8",
                "EDA_path": "",
            },
            "clock": {
                "input_freq": 50_000_000,
                "input_pin": "PIN_25",
            },
            "rst": {
                "input_pin": "PIN_88",
            },
            "spi": {
                "spi_clk_pin": "PIN_106",
                "spi_cs_pin": "PIN_105",
                "spi_mosi_pin": "PIN_104",
                "spi_miso_pin": "PIN_103",
            },
        },
        "components": [
            {
                "type": "uart",
                "name": "uart1",
                "parameters": {
                    "baudrate": 115200,
                    "data_bits": 8,
                    "parity": "none",
                    "stop_bits": 1,
                },
                "pins": {
                    "rxd": "PIN_3",
                    "txd": "PIN_4",
                },
            }
        ],
    }


class UartCodegenTests(unittest.TestCase):
    def test_uart_services_are_loaded_in_expected_order(self) -> None:
        spec = load_project_spec(WORKSPACE_DIR, make_uart_manifest())

        self.assertEqual(spec.total_services, 4)
        self.assertEqual([service.name for service in spec.services], [
            "configure",
            "write_byte",
            "read_byte",
            "get_status",
        ])
        self.assertEqual([service.access for service in spec.services], [
            "input",
            "input",
            "output",
            "output",
        ])
        self.assertEqual([service.data_type for service in spec.services], [
            "u32",
            "u8",
            "u8",
            "u32",
        ])

    def test_uart_artifacts_are_generated(self) -> None:
        spec = load_project_spec(WORKSPACE_DIR, make_uart_manifest())

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            artifacts = generate_artifacts(spec, output_root)

            rtl = artifacts["rtl"].read_text(encoding="utf-8")
            sdk_h = artifacts["sdk_h"].read_text(encoding="utf-8")
            sdk_c = artifacts["sdk_c"].read_text(encoding="utf-8")
            service_map = json.loads(artifacts["service_map"].read_text(encoding="utf-8"))

        self.assertIn("module periphx_uart_adapter", rtl)
        self.assertIn(") u_uart_core (", rtl)
        self.assertIn("periphx_uart_adapter #(", rtl)
        self.assertIn("u_uart1 (", rtl)
        self.assertIn("input wire uart1_rxd", rtl)
        self.assertIn("output wire uart1_txd", rtl)
        self.assertIn("PERIPHX_UART_PARITY_NONE", sdk_h)
        self.assertIn("typedef struct {", sdk_h)
        self.assertIn("periphx_uart_config_t", sdk_h)
        self.assertIn("int periphx_uart1_configure", sdk_h)
        self.assertIn("int periphx_uart1_write_byte", sdk_h)
        self.assertIn("int periphx_uart1_read_byte", sdk_h)
        self.assertIn("int periphx_uart1_get_status", sdk_h)
        self.assertIn("periphx_pack_uart_config", sdk_c)
        self.assertEqual(service_map["total_services"], 4)
        self.assertEqual(
            [service["service_name"] for service in service_map["services"]],
            ["configure", "write_byte", "read_byte", "get_status"],
        )

    def test_sdk_uses_submit_poll_transport_contract(self) -> None:
        spec = load_project_spec(WORKSPACE_DIR, make_uart_manifest())

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(spec, Path(tmp))
            sdk_h = artifacts["sdk_h"].read_text(encoding="utf-8")
            sdk_c = artifacts["sdk_c"].read_text(encoding="utf-8")

        self.assertIn("#define PERIPHX_MSG_POLL", sdk_h)
        self.assertIn("#define PERIPHX_EXCHANGE_LEN", sdk_h)
        self.assertIn("PERIPHX_ERR_BUSY", sdk_h)
        self.assertIn("PERIPHX_ERR_TIMEOUT", sdk_h)
        self.assertIn("typedef uint32_t (*periphx_time_ms_fn)(void *user);", sdk_h)
        self.assertIn("periphx_device_set_time_ms", sdk_h)
        self.assertIn("periphx_call_u32_poll", sdk_h)
        self.assertIn("periphx_call_u32_timeout_ms", sdk_h)
        self.assertIn("periphx_submit_request", sdk_c)
        self.assertIn("periphx_poll_response_once", sdk_c)
        self.assertNotIn("PERIPHX_TRANSACTION_LEN", sdk_h)
        self.assertNotIn("PERIPHX_DEBUG_DEFERRED_READBACK", sdk_h)
        self.assertNotIn("rx_bytes + PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN", sdk_c)

    def test_uart_invalid_manifest_parameters_are_rejected(self) -> None:
        manifest = make_uart_manifest()
        manifest["components"][0]["parameters"]["data_bits"] = 9
        spec = load_project_spec(WORKSPACE_DIR, manifest)

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "uart1.data_bits"):
                generate_artifacts(spec, Path(tmp))

    def test_default_pwm_led_build_still_generates(self) -> None:
        default_manifest = {
            "manifest_version": 1.0,
            "config": make_uart_manifest()["config"],
            "components": [
                {
                    "type": "pwm_led",
                    "name": "pwm_led1",
                    "parameters": {},
                    "pins": {"led_pwm": "PIN_1"},
                }
            ],
        }
        spec = load_project_spec(WORKSPACE_DIR, default_manifest)

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(spec, Path(tmp))
            rtl = artifacts["rtl"].read_text(encoding="utf-8")

        self.assertIn("module periphx_pwm_led_adapter", rtl)
        self.assertNotIn("module periphx_uart_adapter", rtl)


if __name__ == "__main__":
    unittest.main()
