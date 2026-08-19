from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mlr.codegen.artifacts import generate_artifacts
from mlr.project import load_project_spec


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPO_ROOT / "userSpace"


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


def make_i2c_manifest() -> dict:
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
                "type": "i2c",
                "name": "i2c1",
                "parameters": {
                    "clk_div": 250,
                    "stretch_timeout": 1024,
                },
                "pins": {
                    "i2c_scl": "PIN_2",
                    "i2c_sda": "PIN_3",
                },
            }
        ],
    }


class I2cCodegenTests(unittest.TestCase):
    def test_i2c_services_are_loaded_in_expected_order(self) -> None:
        spec = load_project_spec(WORKSPACE_DIR, make_i2c_manifest())

        self.assertEqual(spec.total_services, len(I2C_SERVICE_NAMES))
        self.assertEqual([service.name for service in spec.services], I2C_SERVICE_NAMES)
        self.assertEqual([service.access for service in spec.services], [
            "input",
            "input",
            "input",
            "input",
            "input",
            "input",
            "input",
            "input",
            "output",
            "output",
            "input",
        ])
        self.assertEqual([service.data_type for service in spec.services], [
            "u32",
            "u32",
            "u8",
            "u8",
            "u8",
            "u8",
            "bool",
            "bool",
            "u8",
            "u32",
            "u32",
        ])

    def test_i2c_artifacts_are_generated(self) -> None:
        spec = load_project_spec(WORKSPACE_DIR, make_i2c_manifest())

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(spec, Path(tmp))
            rtl = artifacts["rtl"].read_text(encoding="utf-8")
            sdk_h = artifacts["sdk_h"].read_text(encoding="utf-8")
            sdk_c = artifacts["sdk_c"].read_text(encoding="utf-8")
            service_map = json.loads(artifacts["service_map"].read_text(encoding="utf-8"))

        self.assertIn("module periphx_i2c_adapter", rtl)
        self.assertIn("periphx_i2c_adapter #(", rtl)
        self.assertIn("u_i2c1 (", rtl)
        self.assertIn("inout wire i2c1_i2c_scl", rtl)
        self.assertIn("inout wire i2c1_i2c_sda", rtl)
        self.assertIn(".i2c_scl                 (i2c1_i2c_scl)", rtl)
        self.assertIn(".i2c_sda                 (i2c1_i2c_sda)", rtl)
        self.assertEqual(service_map["total_services"], len(I2C_SERVICE_NAMES))
        self.assertEqual(
            [service["service_name"] for service in service_map["services"]],
            I2C_SERVICE_NAMES,
        )
        self.assertIn("#define PERIPHX_I2C_STATUS_BUSY", sdk_h)
        self.assertIn("#define PERIPHX_I2C_ERR_ADDR_WRITE_NACK", sdk_h)
        self.assertIn("#define PERIPHX_I2C_RESP_OK", sdk_h)
        self.assertIn("typedef struct {", sdk_h)
        self.assertIn("periphx_i2c_config_t", sdk_h)
        self.assertIn("periphx_i2c_transfer_t", sdk_h)
        self.assertIn("int periphx_i2c1_i2c_configure", sdk_h)
        self.assertIn("int periphx_i2c1_i2c_write", sdk_h)
        self.assertIn("int periphx_i2c1_i2c_read", sdk_h)
        self.assertIn("periphx_i2c_check_response", sdk_c)
        self.assertIn("periphx_i2c_transfer_common", sdk_c)


if __name__ == "__main__":
    unittest.main()
