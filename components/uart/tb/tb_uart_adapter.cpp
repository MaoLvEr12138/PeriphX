#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

#include "Vperiphx_uart_adapter.h"
#include "verilated.h"

static vluint64_t sim_time = 0;

static const uint32_t UART_ERR_BAD_CONFIG = 0x00000010u;
static const uint32_t UART_ERR_BUSY = 0x00000013u;
static const uint8_t MSG_REQUEST = 0u;
static const uint8_t MSG_RESPONSE = 1u;
static const uint8_t MSG_ERROR = 3u;

double sc_time_stamp()
{
    return static_cast<double>(sim_time);
}

struct Response {
    uint8_t valid;
    uint8_t msg_type;
    uint32_t payload;
};

class AdapterTb {
public:
    Vperiphx_uart_adapter dut;

    AdapterTb()
    {
        dut.clk = 0;
        dut.rst_n = 0;
        dut.configure_req_valid = 0;
        dut.configure_req_msg_type = 0;
        dut.configure_req_payload = 0;
        dut.write_byte_req_valid = 0;
        dut.write_byte_req_msg_type = 0;
        dut.write_byte_req_payload = 0;
        dut.read_byte_req_valid = 0;
        dut.read_byte_req_msg_type = 0;
        dut.read_byte_req_payload = 0;
        dut.get_status_req_valid = 0;
        dut.get_status_req_msg_type = 0;
        dut.get_status_req_payload = 0;
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
        dut.configure_req_valid = 0;
        dut.configure_req_msg_type = 0;
        dut.configure_req_payload = 0;
        dut.write_byte_req_valid = 0;
        dut.write_byte_req_msg_type = 0;
        dut.write_byte_req_payload = 0;
        dut.read_byte_req_valid = 0;
        dut.read_byte_req_msg_type = 0;
        dut.read_byte_req_payload = 0;
        dut.get_status_req_valid = 0;
        dut.get_status_req_msg_type = 0;
        dut.get_status_req_payload = 0;
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

    Response configure(uint32_t payload)
    {
        dut.configure_req_payload = payload;
        dut.configure_req_msg_type = MSG_REQUEST;
        dut.configure_req_valid = 1;
        tick();
        Response response = {
            static_cast<uint8_t>(dut.configure_rsp_valid),
            static_cast<uint8_t>(dut.configure_rsp_msg_type),
            static_cast<uint32_t>(dut.configure_rsp_payload)
        };
        dut.configure_req_valid = 0;
        tick();
        return response;
    }

    void write_byte(uint8_t value)
    {
        dut.write_byte_req_payload = value;
        dut.write_byte_req_msg_type = MSG_REQUEST;
        dut.write_byte_req_valid = 1;
        tick();
        dut.write_byte_req_valid = 0;
        tick();
    }

    void wait_for_tx_busy()
    {
        bool done = false;
        for(int i = 0; (i < 50) && !done; ++i) {
            dut.get_status_req_payload = 0;
            dut.get_status_req_msg_type = MSG_REQUEST;
            dut.get_status_req_valid = 1;
            tick();
            dut.get_status_req_valid = 0;
            if((dut.get_status_rsp_payload & (1u << 4)) != 0u) {
                done = true;
            } else {
                tick();
            }
        }
        expect(done, "TX did not become busy through adapter");
    }

    void expect(bool condition, const std::string &message)
    {
        if(!condition) {
            throw std::runtime_error(message);
        }
    }
};

static uint32_t pack_config(
    uint16_t baud_div,
    uint8_t data_bits_code,
    uint8_t parity,
    uint8_t stop_bits_code,
    uint32_t reserved)
{
    uint32_t payload = static_cast<uint32_t>(baud_div) & 0xFFFFu;
    payload |= (static_cast<uint32_t>(data_bits_code) & 0x7u) << 16;
    payload |= (static_cast<uint32_t>(parity) & 0x3u) << 19;
    payload |= (static_cast<uint32_t>(stop_bits_code) & 0x1u) << 21;
    payload |= (reserved & 0x3FFu) << 22;
    return payload;
}

static void test_bad_config_returns_error(AdapterTb &tb)
{
    tb.reset();
    Response response = tb.configure(pack_config(0u, 3u, 0u, 0u, 0u));
    tb.expect(response.valid == 1, "bad config response missing");
    tb.expect(response.msg_type == MSG_ERROR, "bad config should return MSG_ERROR");
    tb.expect(response.payload == UART_ERR_BAD_CONFIG, "bad config error code mismatch");
}

static void test_busy_config_returns_error(AdapterTb &tb)
{
    tb.reset();
    Response initial_response = tb.configure(pack_config(200u, 3u, 0u, 0u, 0u));
    tb.expect(initial_response.msg_type == MSG_RESPONSE, "initial config should succeed");
    tb.write_byte(0x33u);
    tb.wait_for_tx_busy();
    Response busy_response = tb.configure(pack_config(16u, 3u, 0u, 0u, 0u));
    tb.expect(busy_response.valid == 1, "busy config response missing");
    tb.expect(busy_response.msg_type == MSG_ERROR, "busy config should return MSG_ERROR");
    tb.expect(busy_response.payload == UART_ERR_BUSY, "busy config error code mismatch");
}

int main(int argc, char **argv)
{
    Verilated::commandArgs(argc, argv);

    int result = 0;
    AdapterTb tb;
    try {
        test_bad_config_returns_error(tb);
        test_busy_config_returns_error(tb);
        std::cout << "PASS: uart_adapter response tests" << std::endl;
    } catch(const std::exception &exc) {
        std::cerr << "FAIL: " << exc.what() << std::endl;
        result = 1;
    }

    return result;
}
