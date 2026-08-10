#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "Vuart_core.h"
#include "verilated.h"
#include "verilated_cov.h"

static vluint64_t sim_time = 0;

static const uint32_t STATUS_RX_EMPTY = (1u << 0);
static const uint32_t STATUS_RX_FULL = (1u << 1);
static const uint32_t STATUS_TX_EMPTY = (1u << 2);
static const uint32_t STATUS_TX_FULL = (1u << 3);
static const uint32_t STATUS_TX_BUSY = (1u << 4);
static const uint32_t STATUS_RX_OVERFLOW = (1u << 5);
static const uint32_t STATUS_PARITY_ERROR = (1u << 6);
static const uint32_t STATUS_FRAME_ERROR = (1u << 7);

static const uint8_t PARITY_NONE = 0u;
static const uint8_t PARITY_ODD = 1u;
static const uint8_t PARITY_EVEN = 2u;

double sc_time_stamp()
{
    return static_cast<double>(sim_time);
}

struct Coverage {
    bool data_bits_5 = false;
    bool data_bits_6 = false;
    bool data_bits_7 = false;
    bool data_bits_8 = false;
    bool parity_none = false;
    bool parity_odd = false;
    bool parity_even = false;
    bool stop_bits_1 = false;
    bool stop_bits_2 = false;
    bool baud_div_fast = false;
    bool baud_div_slow = false;
    bool tx_normal = false;
    bool rx_normal = false;
    bool tx_fifo_full = false;
    bool rx_fifo_empty = false;
    bool rx_fifo_overflow = false;
    bool parity_error = false;
    bool frame_error = false;
    bool configure_success = false;
    bool configure_bad = false;
    bool configure_busy = false;

    void write_report(const char *path) const
    {
        FILE *file = std::fopen(path, "w");
        if(file == nullptr) {
            std::exit(3);
        }
        std::fprintf(file, "data_bits_5=%d\n", data_bits_5);
        std::fprintf(file, "data_bits_6=%d\n", data_bits_6);
        std::fprintf(file, "data_bits_7=%d\n", data_bits_7);
        std::fprintf(file, "data_bits_8=%d\n", data_bits_8);
        std::fprintf(file, "parity_none=%d\n", parity_none);
        std::fprintf(file, "parity_odd=%d\n", parity_odd);
        std::fprintf(file, "parity_even=%d\n", parity_even);
        std::fprintf(file, "stop_bits_1=%d\n", stop_bits_1);
        std::fprintf(file, "stop_bits_2=%d\n", stop_bits_2);
        std::fprintf(file, "baud_div_fast=%d\n", baud_div_fast);
        std::fprintf(file, "baud_div_slow=%d\n", baud_div_slow);
        std::fprintf(file, "tx_normal=%d\n", tx_normal);
        std::fprintf(file, "rx_normal=%d\n", rx_normal);
        std::fprintf(file, "tx_fifo_full=%d\n", tx_fifo_full);
        std::fprintf(file, "rx_fifo_empty=%d\n", rx_fifo_empty);
        std::fprintf(file, "rx_fifo_overflow=%d\n", rx_fifo_overflow);
        std::fprintf(file, "parity_error=%d\n", parity_error);
        std::fprintf(file, "frame_error=%d\n", frame_error);
        std::fprintf(file, "configure_success=%d\n", configure_success);
        std::fprintf(file, "configure_bad=%d\n", configure_bad);
        std::fprintf(file, "configure_busy=%d\n", configure_busy);
        std::fclose(file);
    }
};

class Tb {
public:
    Vuart_core dut;
    Coverage cov;

    Tb()
    {
        dut.clk = 0;
        dut.rst_n = 0;
        dut.cfg_valid = 0;
        dut.cfg_payload = 0;
        dut.tx_write = 0;
        dut.tx_write_data = 0;
        dut.rx_read = 0;
        dut.uart_rxd = 1;
    }

    void tick()
    {
        dut.clk = 0;
        dut.eval();
        sim_time++;
        dut.clk = 1;
        dut.eval();
        sim_time++;
    }

    void reset()
    {
        dut.cfg_valid = 0;
        dut.cfg_payload = 0;
        dut.tx_write = 0;
        dut.tx_write_data = 0;
        dut.rx_read = 0;
        dut.uart_rxd = 1;
        dut.rst_n = 0;
        for(int i = 0; i < 5; ++i) {
            tick();
        }
        dut.rst_n = 1;
        for(int i = 0; i < 3; ++i) {
            tick();
        }
    }

    bool sample_config_bad(uint32_t payload)
    {
        bool is_bad = false;
        dut.cfg_payload = payload;
        dut.cfg_valid = 1;
        dut.eval();
        is_bad = (dut.cfg_bad_config != 0);
        tick();
        dut.cfg_valid = 0;
        tick();
        return is_bad;
    }

    bool sample_config_busy(uint32_t payload)
    {
        bool is_busy = false;
        dut.cfg_payload = payload;
        dut.cfg_valid = 1;
        dut.eval();
        is_busy = (dut.cfg_busy != 0);
        tick();
        dut.cfg_valid = 0;
        tick();
        return is_busy;
    }

    void apply_config(uint32_t payload)
    {
        bool is_bad = sample_config_bad(payload);
        expect(!is_bad, "valid UART config rejected");
    }

    void write_byte(uint8_t value)
    {
        dut.tx_write_data = value;
        dut.tx_write = 1;
        tick();
        dut.tx_write = 0;
        tick();
    }

    uint8_t read_byte()
    {
        uint8_t value = 0u;
        expect(dut.rx_empty == 0, "RX FIFO is empty before read");
        dut.rx_read = 1;
        dut.eval();
        value = static_cast<uint8_t>(dut.rx_read_data & 0xFFu);
        tick();
        dut.rx_read = 0;
        tick();
        return value;
    }

    void drive_cycles(int cycles, uint8_t value)
    {
        dut.uart_rxd = (value != 0u) ? 1 : 0;
        for(int i = 0; i < cycles; ++i) {
            tick();
        }
    }

    void wait_until_rx_not_empty(int max_cycles)
    {
        bool done = false;
        for(int i = 0; (i < max_cycles) && !done; ++i) {
            if(dut.rx_empty == 0) {
                done = true;
            } else {
                tick();
            }
        }
        expect(done, "RX FIFO did not receive data");
    }

    void wait_until_tx_busy(int max_cycles)
    {
        bool done = false;
        for(int i = 0; (i < max_cycles) && !done; ++i) {
            if(dut.tx_busy != 0) {
                done = true;
            } else {
                tick();
            }
        }
        expect(done, "TX did not become busy");
    }

    void expect(bool condition, const std::string &message)
    {
        if(!condition) {
            throw std::runtime_error(message);
        }
    }
};

static uint32_t pack_config_raw(
    uint16_t baud_div,
    uint8_t data_bits_code,
    uint8_t parity,
    uint8_t stop_bits_code,
    uint32_t reserved)
{
    return (static_cast<uint32_t>(baud_div) & 0xFFFFu) |
           ((static_cast<uint32_t>(data_bits_code) & 0x7u) << 16) |
           ((static_cast<uint32_t>(parity) & 0x3u) << 19) |
           ((static_cast<uint32_t>(stop_bits_code) & 0x1u) << 21) |
           ((reserved & 0x3FFu) << 22);
}

static uint32_t pack_config(
    uint16_t baud_div,
    uint8_t data_bits,
    uint8_t parity,
    uint8_t stop_bits)
{
    return pack_config_raw(
        baud_div,
        static_cast<uint8_t>(data_bits - 5u),
        parity,
        static_cast<uint8_t>(stop_bits - 1u),
        0u);
}

static uint8_t data_mask(uint8_t data_bits)
{
    uint8_t mask = 0xFFu;
    if(data_bits == 5u) {
        mask = 0x1Fu;
    } else if(data_bits == 6u) {
        mask = 0x3Fu;
    } else if(data_bits == 7u) {
        mask = 0x7Fu;
    } else {
        mask = 0xFFu;
    }
    return mask;
}

static uint8_t frame_parity(uint8_t value, uint8_t data_bits, uint8_t parity)
{
    uint8_t masked = static_cast<uint8_t>(value & data_mask(data_bits));
    uint8_t bit_xor = 0u;
    for(uint8_t bit = 0u; bit < data_bits; ++bit) {
        bit_xor = static_cast<uint8_t>(bit_xor ^ ((masked >> bit) & 0x1u));
    }
    if(parity == PARITY_ODD) {
        bit_xor = static_cast<uint8_t>(bit_xor ^ 0x1u);
    }
    return static_cast<uint8_t>(bit_xor & 0x1u);
}

static void drive_uart_frame(
    Tb &tb,
    uint8_t value,
    uint8_t data_bits,
    uint8_t parity,
    uint8_t stop_bits,
    uint16_t baud_div,
    bool force_bad_parity,
    bool force_bad_stop)
{
    tb.drive_cycles(static_cast<int>(baud_div) * 2, 1u);
    tb.drive_cycles(static_cast<int>(baud_div), 0u);
    for(uint8_t bit = 0u; bit < data_bits; ++bit) {
        uint8_t bit_value = static_cast<uint8_t>((value >> bit) & 0x1u);
        tb.drive_cycles(static_cast<int>(baud_div), bit_value);
    }
    if(parity != PARITY_NONE) {
        uint8_t parity_bit = frame_parity(value, data_bits, parity);
        if(force_bad_parity) {
            parity_bit = static_cast<uint8_t>(parity_bit ^ 0x1u);
        }
        tb.drive_cycles(static_cast<int>(baud_div), parity_bit);
    }
    for(uint8_t stop = 0u; stop < stop_bits; ++stop) {
        uint8_t stop_value = 1u;
        if(force_bad_stop && (stop == (stop_bits - 1u))) {
            stop_value = 0u;
        }
        tb.drive_cycles(static_cast<int>(baud_div), stop_value);
    }
    tb.drive_cycles(static_cast<int>(baud_div) * 2, 1u);
}

static std::vector<int> capture_tx_frame(
    Tb &tb,
    uint8_t value,
    uint8_t data_bits,
    uint8_t parity,
    uint8_t stop_bits,
    uint16_t baud_div)
{
    std::vector<int> bits;
    int total_bits = 1 + static_cast<int>(data_bits) +
                     ((parity == PARITY_NONE) ? 0 : 1) +
                     static_cast<int>(stop_bits);
    tb.write_byte(value);
    tb.wait_until_tx_busy(static_cast<int>(baud_div) * 4);
    for(int bit = 0; bit < total_bits; ++bit) {
        tb.drive_cycles(static_cast<int>(baud_div) / 2, 1u);
        bits.push_back(tb.dut.uart_txd ? 1 : 0);
        tb.drive_cycles(
            static_cast<int>(baud_div) - (static_cast<int>(baud_div) / 2),
            1u);
    }
    return bits;
}

static void test_reset_status(Tb &tb)
{
    tb.reset();
    tb.expect(tb.dut.tx_empty == 1, "TX FIFO should be empty after reset");
    tb.expect(tb.dut.rx_empty == 1, "RX FIFO should be empty after reset");
}

static void test_all_config_combinations(Tb &tb)
{
    const uint8_t data_bits_values[] = {5u, 6u, 7u, 8u};
    const uint8_t parity_values[] = {PARITY_NONE, PARITY_ODD, PARITY_EVEN};
    const uint8_t stop_values[] = {1u, 2u};

    tb.reset();
    for(uint8_t data_bits : data_bits_values) {
        for(uint8_t parity : parity_values) {
            for(uint8_t stop_bits : stop_values) {
                bool is_bad = tb.sample_config_bad(
                    pack_config(16u, data_bits, parity, stop_bits));
                tb.expect(!is_bad, "valid UART config rejected");
            }
        }
    }
    tb.cov.data_bits_5 = true;
    tb.cov.data_bits_6 = true;
    tb.cov.data_bits_7 = true;
    tb.cov.data_bits_8 = true;
    tb.cov.parity_none = true;
    tb.cov.parity_odd = true;
    tb.cov.parity_even = true;
    tb.cov.stop_bits_1 = true;
    tb.cov.stop_bits_2 = true;
    tb.cov.configure_success = true;

    tb.apply_config(pack_config(4u, 8u, PARITY_NONE, 1u));
    tb.cov.baud_div_fast = true;
    tb.apply_config(pack_config(32u, 8u, PARITY_NONE, 1u));
    tb.cov.baud_div_slow = true;

    tb.expect(tb.sample_config_bad(pack_config(0u, 8u, PARITY_NONE, 1u)),
              "zero baud_div accepted");
    tb.expect(tb.sample_config_bad(pack_config_raw(16u, 4u, PARITY_NONE, 0u, 0u)),
              "invalid data_bits_code accepted");
    tb.expect(tb.sample_config_bad(pack_config_raw(16u, 3u, 3u, 0u, 0u)),
              "invalid parity accepted");
    tb.expect(tb.sample_config_bad(pack_config_raw(16u, 3u, PARITY_NONE, 0u, 1u)),
              "reserved config bits accepted");
    tb.cov.configure_bad = true;
}

static void test_tx_waveforms_for_supported_configs(Tb &tb)
{
    struct TxCase {
        uint8_t value;
        uint8_t data_bits;
        uint8_t parity;
        uint8_t stop_bits;
    };
    const TxCase cases[] = {
        {0x15u, 5u, PARITY_ODD, 1u},
        {0x2Au, 6u, PARITY_EVEN, 2u},
        {0x55u, 7u, PARITY_NONE, 1u},
        {0xA5u, 8u, PARITY_NONE, 1u},
    };

    for(const TxCase &item : cases) {
        tb.reset();
        tb.apply_config(pack_config(8u, item.data_bits, item.parity, item.stop_bits));
        std::vector<int> bits = capture_tx_frame(
            tb,
            item.value,
            item.data_bits,
            item.parity,
            item.stop_bits,
            8u);
        tb.expect(bits[0] == 0, "TX start bit should be low");
        for(uint8_t bit = 0u; bit < item.data_bits; ++bit) {
            int expected = static_cast<int>((item.value >> bit) & 0x1u);
            tb.expect(bits[1 + bit] == expected, "TX data bit mismatch");
        }
        if(item.parity != PARITY_NONE) {
            int parity_index = 1 + static_cast<int>(item.data_bits);
            int expected = static_cast<int>(frame_parity(
                item.value,
                item.data_bits,
                item.parity));
            tb.expect(bits[parity_index] == expected, "TX parity bit mismatch");
        }
        tb.expect(bits.back() == 1, "TX stop bit should be high");
    }
    tb.cov.tx_normal = true;
}

static void test_rx_for_supported_configs(Tb &tb)
{
    struct RxCase {
        uint8_t value;
        uint8_t data_bits;
        uint8_t parity;
        uint8_t stop_bits;
    };
    const RxCase cases[] = {
        {0x1Bu, 5u, PARITY_NONE, 1u},
        {0x2Au, 6u, PARITY_ODD, 2u},
        {0x55u, 7u, PARITY_EVEN, 1u},
        {0xA5u, 8u, PARITY_NONE, 2u},
    };

    for(const RxCase &item : cases) {
        tb.reset();
        tb.apply_config(pack_config(16u, item.data_bits, item.parity, item.stop_bits));
        drive_uart_frame(
            tb,
            item.value,
            item.data_bits,
            item.parity,
            item.stop_bits,
            16u,
            false,
            false);
        tb.wait_until_rx_not_empty(200);
        uint8_t expected = static_cast<uint8_t>(item.value & data_mask(item.data_bits));
        uint8_t actual = tb.read_byte();
        tb.expect(actual == expected, "RX data mismatch");
    }
    tb.cov.rx_normal = true;
}

static void test_tx_fifo_full(Tb &tb)
{
    tb.reset();
    tb.apply_config(pack_config(200u, 8u, PARITY_NONE, 1u));
    for(uint8_t i = 0u; (i < 40u) && (tb.dut.tx_full == 0); ++i) {
        tb.write_byte(i);
    }
    tb.expect(tb.dut.tx_full == 1, "TX FIFO did not become full");
    tb.expect((tb.dut.status & STATUS_TX_FULL) != 0u, "TX full status not set");
    tb.cov.tx_fifo_full = true;
}

static void test_rx_empty_read_status(Tb &tb)
{
    tb.reset();
    tb.apply_config(pack_config(16u, 8u, PARITY_NONE, 1u));
    tb.expect(tb.dut.rx_empty == 1, "RX FIFO should start empty");
    tb.expect((tb.dut.status & STATUS_RX_EMPTY) != 0u, "RX empty status not set");
    tb.dut.rx_read = 1;
    tb.tick();
    tb.dut.rx_read = 0;
    tb.tick();
    tb.expect(tb.dut.rx_empty == 1, "empty RX read should keep FIFO empty");
    tb.cov.rx_fifo_empty = true;
}

static void test_rx_overflow(Tb &tb)
{
    tb.reset();
    tb.apply_config(pack_config(16u, 8u, PARITY_NONE, 1u));
    for(int frame = 0; frame < 17; ++frame) {
        drive_uart_frame(tb, static_cast<uint8_t>(frame), 8u, PARITY_NONE, 1u, 16u, false, false);
    }
    tb.expect((tb.dut.status & STATUS_RX_FULL) != 0u, "RX full status not set");
    tb.expect((tb.dut.status & STATUS_RX_OVERFLOW) != 0u, "RX overflow not recorded");
    tb.cov.rx_fifo_overflow = true;
}

static void test_parity_error(Tb &tb)
{
    tb.reset();
    tb.apply_config(pack_config(16u, 8u, PARITY_ODD, 1u));
    drive_uart_frame(tb, 0x5Au, 8u, PARITY_ODD, 1u, 16u, true, false);
    tb.expect((tb.dut.status & STATUS_PARITY_ERROR) != 0u, "parity error not recorded");
    tb.cov.parity_error = true;
}

static void test_frame_error(Tb &tb)
{
    tb.reset();
    tb.apply_config(pack_config(16u, 8u, PARITY_NONE, 1u));
    drive_uart_frame(tb, 0xC3u, 8u, PARITY_NONE, 1u, 16u, false, true);
    tb.expect((tb.dut.status & STATUS_FRAME_ERROR) != 0u, "frame error not recorded");
    tb.cov.frame_error = true;
}

static void test_config_busy_rejected(Tb &tb)
{
    tb.reset();
    tb.apply_config(pack_config(200u, 8u, PARITY_NONE, 1u));
    tb.write_byte(0x33u);
    tb.wait_until_tx_busy(50);
    tb.expect((tb.dut.status & STATUS_TX_BUSY) != 0u, "TX busy status not set");
    bool is_busy = tb.sample_config_busy(pack_config(16u, 8u, PARITY_NONE, 1u));
    tb.expect(is_busy, "configure while TX busy was not rejected");
    tb.cov.configure_busy = true;
}

int main(int argc, char **argv)
{
    Verilated::commandArgs(argc, argv);
    Verilated::traceEverOn(false);
    VerilatedCov::zero();

    int result = 0;
    Tb tb;
    try {
        test_reset_status(tb);
        test_all_config_combinations(tb);
        test_tx_waveforms_for_supported_configs(tb);
        test_rx_for_supported_configs(tb);
        test_tx_fifo_full(tb);
        test_rx_empty_read_status(tb);
        test_rx_overflow(tb);
        test_parity_error(tb);
        test_frame_error(tb);
        test_config_busy_rejected(tb);
        std::cout << "PASS: uart_core coverage tests" << std::endl;
    } catch(const std::exception &exc) {
        std::cerr << "FAIL: " << exc.what() << std::endl;
        result = 1;
    }

    tb.cov.write_report("functional_coverage.txt");
    VerilatedCov::write("coverage.dat");
    return result;
}
