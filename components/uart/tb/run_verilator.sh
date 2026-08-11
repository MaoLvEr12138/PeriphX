#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
export PYTHONPATH="$(cd ../../.. && pwd)${PYTHONPATH:+:$PYTHONPATH}"
rm -rf obj_dir obj_adapter coverage_report coverage.dat functional_coverage.txt periphx_uart_adapter.v

verilator \
  --cc ../rtl/uart_core.v \
       ../rtl/uart_fifo.v \
       ../rtl/uart_tx.v \
       ../rtl/uart_rx.v \
  --exe tb_uart_core.cpp \
  --top-module uart_core \
  --coverage-line \
  --coverage-toggle \
  --coverage-user \
  -Wno-fatal \
  --build

./obj_dir/Vuart_core
verilator_coverage --annotate coverage_report coverage.dat
python3 check_coverage.py --functional functional_coverage.txt --coverage-dir coverage_report --line-threshold 85

python3 - <<'PY' > periphx_uart_adapter.v
from mlr.codegen.rtl.components.uart import emit_uart_adapter
print("\n".join(emit_uart_adapter()))
PY

verilator \
  --cc periphx_uart_adapter.v \
       ../rtl/uart_core.v \
       ../rtl/uart_fifo.v \
       ../rtl/uart_tx.v \
       ../rtl/uart_rx.v \
  --exe tb_uart_adapter.cpp \
  --top-module periphx_uart_adapter \
  -Mdir obj_adapter \
  -Wno-fatal \
  --build

./obj_adapter/Vperiphx_uart_adapter
