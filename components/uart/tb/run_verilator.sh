#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
rm -rf obj_dir coverage_report coverage.dat functional_coverage.txt

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
