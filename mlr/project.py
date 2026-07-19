from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from mlr.simple_yaml import load_simple_yaml


TYPE_WIDTHS: dict[str, int] = {
    "bool": 1,
    "u8": 8,
    "u32": 32,
}


def sanitize_identifier(value: str) -> str:
    """Return a Verilog/C friendly identifier."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", value)
    if not cleaned:
        return "_"
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def _to_bool(value: Any) -> bool:
    return bool(value)


@dataclass(slots=True)
class ServiceSpec:
    component_type: str
    component_name: str
    name: str
    access: str
    data_type: str
    width: int
    description: str | None = None
    code_hint: int | None = None
    service_id: int = -1

    @property
    def c_macro_name(self) -> str:
        return sanitize_identifier(
            f"PERIPHX_{self.component_name}_{self.name}_ID"
        ).upper()

    @property
    def c_function_name(self) -> str:
        return sanitize_identifier(
            f"periphx_{self.component_name}_{self.name}"
        )

    @property
    def port_prefix(self) -> str:
        return sanitize_identifier(self.name)


@dataclass(slots=True)
class ComponentSpec:
    component_type: str
    name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    pins: dict[str, Any] = field(default_factory=dict)
    services: list[ServiceSpec] = field(default_factory=list)
    interface_path: Path | None = None

    @property
    def module_prefix(self) -> str:
        return sanitize_identifier(f"periphx_{self.component_type}_adapter")

    @property
    def pin_port_names(self) -> dict[str, str]:
        return {
            pin_name: sanitize_identifier(f"{self.name}_{pin_name}")
            for pin_name in self.pins
        }


@dataclass(slots=True)
class ProjectSpec:
    workspace_dir: Path
    manifest_path: Path
    config: dict[str, Any]
    fpga: dict[str, Any]
    clock_pin: str | None
    rst_pin: str | None
    spi_pins: dict[str, str | None]
    components: list[ComponentSpec]
    services: list[ServiceSpec]
    total_services: int


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    data = load_simple_yaml(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")
    return data


def load_project_spec(workspace_dir: Path, manifest_data: dict[str, Any]) -> ProjectSpec:
    repo_root = workspace_dir.parent
    config = manifest_data.get("config", {}) or {}
    fpga = config.get("fpga", {}) or {}
    clock = config.get("clock", {}) or {}
    rst = config.get("rst", {}) or {}
    spi = config.get("spi", {}) or {}

    components_data = manifest_data.get("components", []) or []
    components: list[ComponentSpec] = []
    services: list[ServiceSpec] = []

    for comp_entry in components_data:
        comp_type = str(comp_entry.get("type", "")).strip()
        comp_name = str(comp_entry.get("name", "")).strip()
        if not comp_type:
            raise ValueError("component type cannot be empty")
        if not comp_name:
            raise ValueError(f"component {comp_type} is missing a name")

        interface_path = repo_root / "components" / comp_type / "interface.yml"
        if not interface_path.exists():
            raise FileNotFoundError(f"missing interface file: {interface_path}")

        interface_data = load_simple_yaml(interface_path.read_text(encoding="utf-8")) or {}

        interface_component = str(interface_data.get("component", "")).strip()
        if interface_component and interface_component != comp_type:
            raise ValueError(
                f"interface component mismatch for {comp_name}: "
                f"expected {comp_type}, got {interface_component}"
            )

        service_entries = interface_data.get("services", []) or []
        comp_services: list[ServiceSpec] = []
        for service_entry in service_entries:
            service_name = str(service_entry.get("name", "")).strip()
            access = str(service_entry.get("access", "")).strip().lower()
            data_type = str(service_entry.get("type", "")).strip()
            description = service_entry.get("description")
            code_hint_raw = service_entry.get("code")
            code_hint = int(code_hint_raw, 0) if isinstance(code_hint_raw, str) else code_hint_raw

            if not service_name:
                raise ValueError(f"service entry in {comp_name} is missing a name")
            if access not in {"input", "output"}:
                raise ValueError(
                    f"service {comp_name}.{service_name} has unsupported access: {access}"
                )
            if data_type not in TYPE_WIDTHS:
                raise ValueError(
                    f"service {comp_name}.{service_name} has unsupported type: {data_type}"
                )

            spec = ServiceSpec(
                component_type=comp_type,
                component_name=comp_name,
                name=service_name,
                access=access,
                data_type=data_type,
                width=TYPE_WIDTHS[data_type],
                description=description if isinstance(description, str) else None,
                code_hint=int(code_hint) if code_hint is not None else None,
            )
            comp_services.append(spec)
            services.append(spec)

        components.append(
            ComponentSpec(
                component_type=comp_type,
                name=comp_name,
                parameters=comp_entry.get("parameters", {}) or {},
                pins=comp_entry.get("pins", {}) or {},
                services=comp_services,
                interface_path=interface_path,
            )
        )

    for service_id, service in enumerate(services):
        service.service_id = service_id

    return ProjectSpec(
        workspace_dir=workspace_dir,
        manifest_path=workspace_dir / "manifest.yaml",
        config=config,
        fpga=fpga,
        clock_pin=clock.get("input_pin"),
        rst_pin=rst.get("input_pin"),
        spi_pins={
            "spi_clk_pin": spi.get("spi_clk_pin"),
            "spi_cs_pin": spi.get("spi_cs_pin"),
            "spi_mosi_pin": spi.get("spi_mosi_pin"),
            "spi_miso_pin": spi.get("spi_miso_pin"),
        },
        components=components,
        services=services,
        total_services=len(services),
    )
