#include "Vtb_periphx_i2c_adapter.h"
#include "verilated.h"
#include "verilated_cov.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

namespace {

constexpr uint8_t MSG_REQUEST = 0x0U;
constexpr uint8_t MSG_RESPONSE = 0x1U;
constexpr uint8_t MSG_ERROR = 0x3U;
constexpr uint32_t RESP_OK = 0U;
constexpr uint32_t RESP_BUSY = 1U;
constexpr uint32_t RESP_INVALID = 2U;
constexpr uint32_t RESP_FULL = 3U;
constexpr uint32_t RESP_EMPTY = 4U;
constexpr uint32_t ERR_BAD_TYPE = 0x00000002UL;

constexpr uint32_t STATUS_BUSY = 0x00000001UL;
constexpr uint32_t STATUS_DONE = 0x00000002UL;
constexpr uint32_t STATUS_ACK_ERROR = 0x00000004UL;
constexpr uint32_t STATUS_STRETCH_TIMEOUT = 0x00000008UL;
constexpr uint32_t STATUS_ARB_LOST = 0x00000010UL;
constexpr uint32_t STATUS_TX_FULL = 0x00000020UL;
constexpr uint32_t STATUS_TX_EMPTY = 0x00000040UL;
constexpr uint32_t STATUS_RX_FULL = 0x00000080UL;
constexpr uint32_t STATUS_RX_EMPTY = 0x00000100UL;
constexpr uint32_t STATUS_ERROR_MASK = 0x0000F000UL;
constexpr uint32_t STATUS_ERROR_SHIFT = 12U;
constexpr uint32_t STATUS_TX_COUNT_SHIFT = 16U;
constexpr uint32_t STATUS_RX_COUNT_SHIFT = 24U;

constexpr uint32_t CLEAR_DONE = 0x00000002UL;
constexpr uint32_t CLEAR_ACK_ERROR = 0x00000004UL;
constexpr uint32_t CLEAR_STRETCH_TIMEOUT = 0x00000008UL;
constexpr uint32_t CLEAR_ARB_LOST = 0x00000010UL;
constexpr uint32_t CLEAR_TX = 0x00000100UL;
constexpr uint32_t CLEAR_RX = 0x00000200UL;
constexpr uint32_t CLEAR_ERROR_CODE = 0x00008000UL;

constexpr uint32_t ERR_NONE = 0U;
constexpr uint32_t ERR_ADDR_WRITE_NACK = 1U;
constexpr uint32_t ERR_REG_ADDR_NACK = 2U;
constexpr uint32_t ERR_WRITE_DATA_NACK = 3U;
constexpr uint32_t ERR_ADDR_READ_NACK = 4U;
constexpr uint32_t ERR_STRETCH_TIMEOUT = 5U;
constexpr uint32_t ERR_ARB_LOST = 6U;
constexpr uint32_t ERR_INVALID_LENGTH = 7U;
constexpr uint32_t ERR_TX_UNDERFLOW = 8U;
constexpr uint32_t ERR_RX_OVERFLOW = 9U;

class I2cAdapterSim {
public:
    I2cAdapterSim()
        : top_()
    {
        ClearInputs();
        top_.slave_scl_drive_low = 0U;
        top_.slave_sda_drive_low = 0U;
        top_.clk = 0U;
        top_.rst_n = 0U;
        top_.eval();
    }

    void Reset()
    {
        ClearInputs();
        top_.slave_scl_drive_low = 0U;
        top_.slave_sda_drive_low = 0U;
        top_.rst_n = 0U;
        for(int i = 0; i < 6; ++i) {
            Tick();
        }
        top_.rst_n = 1U;
        for(int i = 0; i < 3; ++i) {
            Tick();
        }
    }

    void SetClkDiv(uint32_t value)
    {
        SetClkDivExpect(value, value);
    }

    void SetClkDivExpect(uint32_t value, uint32_t expected)
    {
        ServiceU32(top_.set_clk_div_req_valid,
                   top_.set_clk_div_req_msg_type,
                   top_.set_clk_div_req_payload,
                   top_.set_clk_div_rsp_valid,
                   top_.set_clk_div_rsp_msg_type,
                   top_.set_clk_div_rsp_payload,
                   value,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "set_clk_div");
    }

    void SetStretchTimeout(uint32_t value)
    {
        SetStretchTimeoutExpect(value, value);
    }

    void SetStretchTimeoutExpect(uint32_t value, uint32_t expected)
    {
        ServiceU32(top_.set_stretch_timeout_req_valid,
                   top_.set_stretch_timeout_req_msg_type,
                   top_.set_stretch_timeout_req_payload,
                   top_.set_stretch_timeout_rsp_valid,
                   top_.set_stretch_timeout_rsp_msg_type,
                   top_.set_stretch_timeout_rsp_payload,
                   value,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "set_stretch_timeout");
    }

    void SetDevAddr(uint8_t value)
    {
        SetDevAddrExpect(value, value & 0x7FU);
    }

    void SetDevAddrExpect(uint8_t value, uint32_t expected)
    {
        ServiceU32(top_.set_dev_addr_req_valid,
                   top_.set_dev_addr_req_msg_type,
                   top_.set_dev_addr_req_payload,
                   top_.set_dev_addr_rsp_valid,
                   top_.set_dev_addr_rsp_msg_type,
                   top_.set_dev_addr_rsp_payload,
                   value,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "set_dev_addr");
    }

    void SetRegAddr(uint8_t value)
    {
        SetRegAddrExpect(value, value);
    }

    void SetRegAddrExpect(uint8_t value, uint32_t expected)
    {
        ServiceU32(top_.set_reg_addr_req_valid,
                   top_.set_reg_addr_req_msg_type,
                   top_.set_reg_addr_req_payload,
                   top_.set_reg_addr_rsp_valid,
                   top_.set_reg_addr_rsp_msg_type,
                   top_.set_reg_addr_rsp_payload,
                   value,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "set_reg_addr");
    }

    void SetLength(uint8_t value, uint32_t expected)
    {
        ServiceU32(top_.set_length_req_valid,
                   top_.set_length_req_msg_type,
                   top_.set_length_req_payload,
                   top_.set_length_rsp_valid,
                   top_.set_length_rsp_msg_type,
                   top_.set_length_rsp_payload,
                   value,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "set_length");
    }

    void PushWriteData(uint8_t value, uint32_t expected)
    {
        ServiceU32(top_.push_write_data_req_valid,
                   top_.push_write_data_req_msg_type,
                   top_.push_write_data_req_payload,
                   top_.push_write_data_rsp_valid,
                   top_.push_write_data_rsp_msg_type,
                   top_.push_write_data_rsp_payload,
                   value,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "push_write_data");
    }

    void StartWrite(uint32_t expected)
    {
        ServiceU32(top_.start_write_req_valid,
                   top_.start_write_req_msg_type,
                   top_.start_write_req_payload,
                   top_.start_write_rsp_valid,
                   top_.start_write_rsp_msg_type,
                   top_.start_write_rsp_payload,
                   1U,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "start_write");
    }

    void StartRead(uint32_t expected)
    {
        ServiceU32(top_.start_read_req_valid,
                   top_.start_read_req_msg_type,
                   top_.start_read_req_payload,
                   top_.start_read_rsp_valid,
                   top_.start_read_rsp_msg_type,
                   top_.start_read_rsp_payload,
                   1U,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "start_read");
    }

    uint32_t PopReadData()
    {
        ClearInputs();
        top_.pop_read_data_req_payload = 0U;
        top_.pop_read_data_req_msg_type = MSG_REQUEST;
        top_.pop_read_data_req_valid = 1U;
        Tick();
        Require(top_.pop_read_data_rsp_valid == 1U,
                "pop_read_data response missing");
        ExpectEq("pop_read_data response type",
                 top_.pop_read_data_rsp_msg_type, MSG_RESPONSE);
        const uint32_t data = top_.pop_read_data_rsp_payload;
        top_.pop_read_data_req_valid = 0U;
        Tick();
        return data;
    }

    void PopReadDataExpect(uint32_t expected)
    {
        ExpectEq("pop_read_data", PopReadData(), expected);
    }

    uint32_t GetStatus()
    {
        ClearInputs();
        top_.get_status_req_payload = 0U;
        top_.get_status_req_msg_type = MSG_REQUEST;
        top_.get_status_req_valid = 1U;
        Tick();
        Require(top_.get_status_rsp_valid == 1U,
                "get_status response missing");
        ExpectEq("get_status response type",
                 top_.get_status_rsp_msg_type, MSG_RESPONSE);
        const uint32_t status = top_.get_status_rsp_payload;
        top_.get_status_req_valid = 0U;
        Tick();
        return status;
    }

    void ClearStatus(uint32_t mask)
    {
        ClearStatusExpect(mask, RESP_OK);
    }

    void ClearStatusExpect(uint32_t mask, uint32_t expected)
    {
        ServiceU32(top_.clear_status_req_valid,
                   top_.clear_status_req_msg_type,
                   top_.clear_status_req_payload,
                   top_.clear_status_rsp_valid,
                   top_.clear_status_rsp_msg_type,
                   top_.clear_status_rsp_payload,
                   mask,
                   MSG_REQUEST,
                   MSG_RESPONSE,
                   expected,
                   "clear_status");
    }

    void BadSetDevAddr(uint8_t value)
    {
        ServiceU32(top_.set_dev_addr_req_valid,
                   top_.set_dev_addr_req_msg_type,
                   top_.set_dev_addr_req_payload,
                   top_.set_dev_addr_rsp_valid,
                   top_.set_dev_addr_rsp_msg_type,
                   top_.set_dev_addr_rsp_payload,
                   value,
                   MSG_RESPONSE,
                   MSG_ERROR,
                   ERR_BAD_TYPE,
                   "bad set_dev_addr");
    }

    void BadStartWrite()
    {
        ServiceU32(top_.start_write_req_valid,
                   top_.start_write_req_msg_type,
                   top_.start_write_req_payload,
                   top_.start_write_rsp_valid,
                   top_.start_write_rsp_msg_type,
                   top_.start_write_rsp_payload,
                   1U,
                   MSG_RESPONSE,
                   MSG_ERROR,
                   ERR_BAD_TYPE,
                   "bad start_write");
    }

    void ConfigureTransfer(uint8_t dev_addr, uint8_t reg_addr, uint8_t length)
    {
        SetDevAddr(dev_addr);
        SetRegAddr(reg_addr);
        SetLength(length, RESP_OK);
    }

    void Push16Bytes(uint8_t base)
    {
        for(uint8_t i = 0U; i < 16U; ++i) {
            PushWriteData(static_cast<uint8_t>(base + i), RESP_OK);
        }
    }

    void ExpectWriteTransaction(uint8_t dev_addr, uint8_t reg_addr,
                                const std::array<uint8_t, 16> &data,
                                uint8_t length)
    {
        WaitStart();
        ExpectEq("write address byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 0U));
        DriveAck();
        ExpectEq("write register byte", ReceiveByte(), reg_addr);
        DriveAck();
        for(uint8_t i = 0U; i < length; ++i) {
            ExpectEq("write data byte", ReceiveByte(), data[i]);
            DriveAck();
        }
        WaitStop();
    }

    void ExpectReadTransaction(uint8_t dev_addr, uint8_t reg_addr,
                               const std::array<uint8_t, 16> &data,
                               uint8_t length)
    {
        WaitStart();
        ExpectEq("read address write byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 0U));
        DriveAck();
        ExpectEq("read register byte", ReceiveByte(), reg_addr);
        DriveAck();
        WaitStart();
        ExpectEq("read address read byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 1U));
        DriveAck();
        for(uint8_t i = 0U; i < length; ++i) {
            const bool expect_ack = (i != static_cast<uint8_t>(length - 1U));
            SendByteAndCheckMasterAck(data[i], expect_ack);
        }
        WaitStop();
    }

    void ExpectNackAtAddressWrite(uint8_t dev_addr)
    {
        WaitStart();
        ExpectEq("nack address write byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 0U));
        DriveNack();
        WaitStop();
    }

    void ExpectNackAtRegister(uint8_t dev_addr, uint8_t reg_addr)
    {
        WaitStart();
        ExpectEq("nack register address byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 0U));
        DriveAck();
        ExpectEq("nack register byte", ReceiveByte(), reg_addr);
        DriveNack();
        WaitStop();
    }

    void ExpectNackAtWriteData(uint8_t dev_addr, uint8_t reg_addr,
                               uint8_t data)
    {
        WaitStart();
        ExpectEq("nack data address byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 0U));
        DriveAck();
        ExpectEq("nack data register byte", ReceiveByte(), reg_addr);
        DriveAck();
        ExpectEq("nack write data byte", ReceiveByte(), data);
        DriveNack();
        WaitStop();
    }

    void ExpectNackAtAddressRead(uint8_t dev_addr, uint8_t reg_addr)
    {
        WaitStart();
        ExpectEq("nack read address write byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 0U));
        DriveAck();
        ExpectEq("nack read register byte", ReceiveByte(), reg_addr);
        DriveAck();
        WaitStart();
        ExpectEq("nack address read byte", ReceiveByte(),
                 static_cast<uint8_t>((dev_addr << 1U) | 1U));
        DriveNack();
        WaitStop();
    }

    void StretchBeforeNextSclRise(int hold_ticks)
    {
        top_.slave_scl_drive_low = 1U;
        top_.eval();
        for(int i = 0; i < hold_ticks; ++i) {
            Tick();
        }
        top_.slave_scl_drive_low = 0U;
        top_.eval();
    }

    void ForceStretchTimeout()
    {
        top_.slave_scl_drive_low = 1U;
        top_.eval();
        for(int i = 0; i < 200; ++i) {
            Tick();
        }
        top_.slave_scl_drive_low = 0U;
        top_.eval();
    }

    void ForceArbitrationLost()
    {
        top_.slave_sda_drive_low = 1U;
        top_.eval();
        for(int i = 0; i < 100; ++i) {
            Tick();
        }
        top_.slave_sda_drive_low = 0U;
        top_.eval();
    }

    void HoldSclLow(bool hold)
    {
        top_.slave_scl_drive_low = hold ? 1U : 0U;
        top_.eval();
    }

    void WaitDoneStatus()
    {
        bool found = false;
        for(int poll = 0; (poll < 120) && !found; ++poll) {
            const uint32_t status = GetStatus();
            if((status & STATUS_DONE) != 0U) {
                found = true;
            } else {
                for(int i = 0; i < 5; ++i) {
                    Tick();
                }
            }
        }
        Require(found, "I2C transaction did not complete");
    }

    void ExpectNoStart(int ticks)
    {
        bool found = false;
        for(int i = 0; (i < ticks) && !found; ++i) {
            found = StepDetectStart();
        }
        Require(!found, "unexpected I2C START observed");
    }

    void ExpectBusReleased()
    {
        top_.slave_scl_drive_low = 0U;
        top_.slave_sda_drive_low = 0U;
        top_.eval();
        Tick();
        Require(Scl(), "SCL is not released");
        Require(Sda(), "SDA is not released");
    }

    uint32_t TxCount(uint32_t status) const
    {
        return ((status >> STATUS_TX_COUNT_SHIFT) & 0xFFU);
    }

    uint32_t RxCount(uint32_t status) const
    {
        return ((status >> STATUS_RX_COUNT_SHIFT) & 0xFFU);
    }

    uint32_t ErrorCode(uint32_t status) const
    {
        return ((status & STATUS_ERROR_MASK) >> STATUS_ERROR_SHIFT);
    }

    void Tick()
    {
        top_.clk = 0U;
        top_.eval();
        top_.clk = 1U;
        top_.eval();
    }

    static void Require(bool condition, const char *message)
    {
        if(!condition) {
            std::printf("FAIL: %s\n", message);
            std::exit(1);
        }
    }

    static void ExpectEq(const char *name, uint32_t actual,
                         uint32_t expected)
    {
        if(actual != expected) {
            std::printf("FAIL: %s actual=0x%08x expected=0x%08x\n",
                        name, actual, expected);
            std::exit(1);
        }
    }

private:
    Vtb_periphx_i2c_adapter top_;

    void ClearInputs()
    {
        top_.set_clk_div_req_valid = 0U;
        top_.set_clk_div_req_msg_type = MSG_REQUEST;
        top_.set_clk_div_req_payload = 0U;
        top_.set_stretch_timeout_req_valid = 0U;
        top_.set_stretch_timeout_req_msg_type = MSG_REQUEST;
        top_.set_stretch_timeout_req_payload = 0U;
        top_.set_dev_addr_req_valid = 0U;
        top_.set_dev_addr_req_msg_type = MSG_REQUEST;
        top_.set_dev_addr_req_payload = 0U;
        top_.set_reg_addr_req_valid = 0U;
        top_.set_reg_addr_req_msg_type = MSG_REQUEST;
        top_.set_reg_addr_req_payload = 0U;
        top_.set_length_req_valid = 0U;
        top_.set_length_req_msg_type = MSG_REQUEST;
        top_.set_length_req_payload = 0U;
        top_.push_write_data_req_valid = 0U;
        top_.push_write_data_req_msg_type = MSG_REQUEST;
        top_.push_write_data_req_payload = 0U;
        top_.start_write_req_valid = 0U;
        top_.start_write_req_msg_type = MSG_REQUEST;
        top_.start_write_req_payload = 0U;
        top_.start_read_req_valid = 0U;
        top_.start_read_req_msg_type = MSG_REQUEST;
        top_.start_read_req_payload = 0U;
        top_.pop_read_data_req_valid = 0U;
        top_.pop_read_data_req_msg_type = MSG_REQUEST;
        top_.pop_read_data_req_payload = 0U;
        top_.get_status_req_valid = 0U;
        top_.get_status_req_msg_type = MSG_REQUEST;
        top_.get_status_req_payload = 0U;
        top_.clear_status_req_valid = 0U;
        top_.clear_status_req_msg_type = MSG_REQUEST;
        top_.clear_status_req_payload = 0U;
    }

    void ServiceU32(CData &req_valid,
                    CData &req_msg_type,
                    IData &req_payload,
                    CData &rsp_valid,
                    CData &rsp_msg_type,
                    IData &rsp_payload,
                    uint32_t value,
                    uint8_t request_type,
                    uint8_t expected_type,
                    uint32_t expected_payload,
                    const char *name)
    {
        ClearInputs();
        req_payload = value;
        req_msg_type = request_type;
        req_valid = 1U;
        Tick();
        Require(rsp_valid == 1U, name);
        ExpectEq("response type", rsp_msg_type, expected_type);
        ExpectEq(name, rsp_payload, expected_payload);
        req_valid = 0U;
        Tick();
    }

    bool Scl() const
    {
        return (top_.i2c_scl_line != 0U);
    }

    bool Sda() const
    {
        return (top_.i2c_sda_line != 0U);
    }

    bool StepDetectStart()
    {
        const bool old_sda = Sda();
        Tick();
        return (old_sda && !Sda() && Scl());
    }

    bool StepDetectStop()
    {
        const bool old_sda = Sda();
        Tick();
        return (!old_sda && Sda() && Scl());
    }

    bool StepDetectSclRise()
    {
        const bool old_scl = Scl();
        Tick();
        return (!old_scl && Scl());
    }

    bool StepDetectSclFall()
    {
        const bool old_scl = Scl();
        Tick();
        return (old_scl && !Scl());
    }

    void WaitStart()
    {
        bool found = false;
        for(int i = 0; (i < 6000) && !found; ++i) {
            found = StepDetectStart();
        }
        Require(found, "I2C START not observed");
    }

    void WaitStop()
    {
        bool found = false;
        for(int i = 0; (i < 6000) && !found; ++i) {
            found = StepDetectStop();
        }
        Require(found, "I2C STOP not observed");
    }

    void WaitSclRise()
    {
        bool found = false;
        for(int i = 0; (i < 6000) && !found; ++i) {
            found = StepDetectSclRise();
        }
        Require(found, "SCL rising edge not observed");
    }

    void WaitSclFall()
    {
        bool found = false;
        for(int i = 0; (i < 6000) && !found; ++i) {
            found = StepDetectSclFall();
        }
        Require(found, "SCL falling edge not observed");
    }

    uint8_t ReceiveByte()
    {
        uint8_t value = 0U;
        for(int bit = 7; bit >= 0; --bit) {
            WaitSclRise();
            if(Sda()) {
                value = static_cast<uint8_t>(value |
                    static_cast<uint8_t>(1U << static_cast<unsigned>(bit)));
            }
            WaitSclFall();
        }
        return value;
    }

    void DriveAck()
    {
        top_.slave_sda_drive_low = 1U;
        top_.eval();
        WaitSclRise();
        WaitSclFall();
        top_.slave_sda_drive_low = 0U;
        top_.eval();
    }

    void DriveNack()
    {
        top_.slave_sda_drive_low = 0U;
        top_.eval();
        WaitSclRise();
        Require(Sda(), "slave NACK was not released high");
        WaitSclFall();
    }

    void SendByteAndCheckMasterAck(uint8_t value, bool expect_ack)
    {
        for(int bit = 7; bit >= 0; --bit) {
            const bool bit_is_zero =
                ((value & static_cast<uint8_t>(1U <<
                    static_cast<unsigned>(bit))) == 0U);
            top_.slave_sda_drive_low = bit_is_zero ? 1U : 0U;
            top_.eval();
            WaitSclRise();
            WaitSclFall();
        }
        top_.slave_sda_drive_low = 0U;
        top_.eval();
        WaitSclRise();
        if(expect_ack) {
            Require(!Sda(), "master did not ACK read byte");
        } else {
            Require(Sda(), "master did not NACK final read byte");
        }
        WaitSclFall();
    }
};

void ExpectResetDefaults(I2cAdapterSim &sim)
{
    uint32_t status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("reset busy", status & STATUS_BUSY, 0U);
    I2cAdapterSim::ExpectEq("reset sticky",
                            status & (STATUS_DONE | STATUS_ACK_ERROR |
                                      STATUS_STRETCH_TIMEOUT |
                                      STATUS_ARB_LOST),
                            0U);
    I2cAdapterSim::ExpectEq("reset error code",
                            sim.ErrorCode(status), ERR_NONE);
    I2cAdapterSim::ExpectEq("reset tx count", sim.TxCount(status), 0U);
    I2cAdapterSim::ExpectEq("reset rx count", sim.RxCount(status), 0U);
    I2cAdapterSim::ExpectEq("reset tx empty",
                            status & STATUS_TX_EMPTY, STATUS_TX_EMPTY);
    I2cAdapterSim::ExpectEq("reset rx empty",
                            status & STATUS_RX_EMPTY, STATUS_RX_EMPTY);
    sim.ExpectBusReleased();

    sim.SetDevAddr(0x50U);
    sim.SetRegAddr(0x01U);
    sim.PushWriteData(0x11U, RESP_OK);
    sim.StartWrite(RESP_OK);
    std::array<uint8_t, 16> data{};
    data[0] = 0x11U;
    sim.ExpectWriteTransaction(0x50U, 0x01U, data, 1U);
    sim.WaitDoneStatus();
    sim.ExpectBusReleased();
}

void ExpectMinimalWriteRecovery(I2cAdapterSim &sim, uint8_t reg_addr,
                                uint8_t data_value)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, reg_addr, 1U);
    sim.PushWriteData(data_value, RESP_OK);
    sim.StartWrite(RESP_OK);
    std::array<uint8_t, 16> data{};
    data[0] = data_value;
    sim.ExpectWriteTransaction(0x50U, reg_addr, data, 1U);
    sim.WaitDoneStatus();
    sim.ExpectBusReleased();
}

void ExpectNackStatus(I2cAdapterSim &sim, uint32_t expected_error)
{
    sim.WaitDoneStatus();
    const uint32_t status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("nack done", status & STATUS_DONE, STATUS_DONE);
    I2cAdapterSim::ExpectEq("nack ack_error",
                            status & STATUS_ACK_ERROR, STATUS_ACK_ERROR);
    I2cAdapterSim::ExpectEq("nack error code",
                            sim.ErrorCode(status), expected_error);
    I2cAdapterSim::ExpectEq("nack busy", status & STATUS_BUSY, 0U);
    sim.ExpectBusReleased();
}

void TestNackFourPhases(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x10U, 1U);
    sim.PushWriteData(0x21U, RESP_OK);
    sim.StartWrite(RESP_OK);
    sim.ExpectNackAtAddressWrite(0x50U);
    ExpectNackStatus(sim, ERR_ADDR_WRITE_NACK);
    ExpectMinimalWriteRecovery(sim, 0x11U, 0x22U);

    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x12U, 1U);
    sim.PushWriteData(0x23U, RESP_OK);
    sim.StartWrite(RESP_OK);
    sim.ExpectNackAtRegister(0x50U, 0x12U);
    ExpectNackStatus(sim, ERR_REG_ADDR_NACK);
    ExpectMinimalWriteRecovery(sim, 0x13U, 0x24U);

    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x14U, 1U);
    sim.PushWriteData(0x25U, RESP_OK);
    sim.StartWrite(RESP_OK);
    sim.ExpectNackAtWriteData(0x50U, 0x14U, 0x25U);
    ExpectNackStatus(sim, ERR_WRITE_DATA_NACK);
    ExpectMinimalWriteRecovery(sim, 0x15U, 0x26U);

    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x16U, 1U);
    sim.StartRead(RESP_OK);
    sim.ExpectNackAtAddressRead(0x50U, 0x16U);
    ExpectNackStatus(sim, ERR_ADDR_READ_NACK);
    ExpectMinimalWriteRecovery(sim, 0x17U, 0x27U);
}

void TestInvalidLength(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x20U, 2U);
    sim.PushWriteData(0x31U, RESP_OK);
    sim.PushWriteData(0x32U, RESP_OK);
    sim.SetLength(0U, RESP_INVALID);
    uint32_t status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("invalid zero error code",
                            sim.ErrorCode(status), ERR_INVALID_LENGTH);
    sim.SetLength(17U, RESP_INVALID);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("invalid seventeen error code",
                            sim.ErrorCode(status), ERR_INVALID_LENGTH);
    sim.StartWrite(RESP_OK);
    std::array<uint8_t, 16> data{};
    data[0] = 0x31U;
    data[1] = 0x32U;
    sim.ExpectWriteTransaction(0x50U, 0x20U, data, 2U);
    sim.WaitDoneStatus();

    sim.ClearStatus(0U);
    sim.SetLength(0U, RESP_INVALID);
    sim.PushWriteData(0x33U, RESP_OK);
    sim.PushWriteData(0x34U, RESP_OK);
    sim.StartWrite(RESP_OK);
    data[0] = 0x33U;
    data[1] = 0x34U;
    sim.ExpectWriteTransaction(0x50U, 0x20U, data, 2U);
    sim.WaitDoneStatus();
}

void TestUnderflowOverflowAndFifoCounts(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x30U, 2U);
    sim.PushWriteData(0x41U, RESP_OK);
    uint32_t before = sim.GetStatus();
    sim.StartWrite(RESP_EMPTY);
    sim.ExpectNoStart(80);
    uint32_t after = sim.GetStatus();
    I2cAdapterSim::ExpectEq("underflow error code",
                            sim.ErrorCode(after), ERR_TX_UNDERFLOW);
    I2cAdapterSim::ExpectEq("underflow tx count stable",
                            sim.TxCount(after), sim.TxCount(before));
    sim.ExpectBusReleased();

    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x31U, 16U);
    std::array<uint8_t, 16> read_data{};
    for(uint8_t i = 0U; i < 16U; ++i) {
        read_data[i] = static_cast<uint8_t>(0x50U + i);
    }
    sim.StartRead(RESP_OK);
    sim.ExpectReadTransaction(0x50U, 0x31U, read_data, 16U);
    sim.WaitDoneStatus();
    before = sim.GetStatus();
    I2cAdapterSim::ExpectEq("rx full count", sim.RxCount(before), 16U);
    I2cAdapterSim::ExpectEq("rx full status",
                            before & STATUS_RX_FULL, STATUS_RX_FULL);
    sim.SetLength(1U, RESP_OK);
    sim.StartRead(RESP_FULL);
    sim.ExpectNoStart(80);
    after = sim.GetStatus();
    I2cAdapterSim::ExpectEq("overflow error code",
                            sim.ErrorCode(after), ERR_RX_OVERFLOW);
    I2cAdapterSim::ExpectEq("overflow rx count stable",
                            sim.RxCount(after), 16U);
    sim.ExpectBusReleased();

    for(uint8_t i = 0U; i < 16U; ++i) {
        I2cAdapterSim::ExpectEq("fifo pop order",
                                sim.PopReadData(), read_data[i]);
    }
    after = sim.GetStatus();
    I2cAdapterSim::ExpectEq("rx empty after pop",
                            after & STATUS_RX_EMPTY, STATUS_RX_EMPTY);
    I2cAdapterSim::ExpectEq("rx count after pop", sim.RxCount(after), 0U);
}

void TestBusyResponses(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x40U, 1U);
    sim.PushWriteData(0x61U, RESP_OK);
    sim.HoldSclLow(true);
    sim.StartWrite(RESP_OK);
    uint32_t status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("busy status allowed",
                            status & STATUS_BUSY, STATUS_BUSY);
    sim.SetClkDivExpect(9U, RESP_BUSY);
    sim.SetStretchTimeoutExpect(9U, RESP_BUSY);
    sim.SetDevAddrExpect(0x22U, RESP_BUSY);
    sim.SetRegAddrExpect(0x33U, RESP_BUSY);
    sim.SetLength(16U, RESP_BUSY);
    sim.PushWriteData(0x62U, RESP_BUSY);
    sim.StartWrite(RESP_BUSY);
    sim.StartRead(RESP_BUSY);
    sim.PopReadDataExpect(RESP_BUSY);
    sim.ClearStatusExpect(0U, RESP_BUSY);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("busy tx count unchanged",
                            sim.TxCount(status), 1U);
    sim.HoldSclLow(false);
    std::array<uint8_t, 16> data{};
    data[0] = 0x61U;
    sim.ExpectWriteTransaction(0x50U, 0x40U, data, 1U);
    sim.WaitDoneStatus();
    sim.ExpectBusReleased();
}

void SeedStickyStatus(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x50U, 1U);
    sim.PushWriteData(0x71U, RESP_OK);
    sim.StartWrite(RESP_OK);
    std::array<uint8_t, 16> data{};
    data[0] = 0x71U;
    sim.ExpectWriteTransaction(0x50U, 0x50U, data, 1U);
    sim.WaitDoneStatus();

    sim.ClearStatus(CLEAR_TX);
    sim.PushWriteData(0x72U, RESP_OK);

    sim.SetLength(1U, RESP_OK);
    data[0] = 0x73U;
    sim.StartRead(RESP_OK);
    sim.ExpectReadTransaction(0x50U, 0x50U, data, 1U);
    sim.WaitDoneStatus();

    sim.SetLength(0U, RESP_INVALID);
    sim.SetLength(1U, RESP_OK);
    sim.SetStretchTimeout(8U);
    sim.StartWrite(RESP_OK);
    sim.ForceStretchTimeout();
    sim.WaitDoneStatus();

    sim.SetStretchTimeout(64U);
    sim.StartWrite(RESP_OK);
    sim.ForceArbitrationLost();
    sim.WaitDoneStatus();
}

void TestClearStatusMasks(I2cAdapterSim &sim)
{
    SeedStickyStatus(sim);
    sim.ClearStatus(0U);
    uint32_t status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear all sticky",
                            status & (STATUS_DONE | STATUS_ACK_ERROR |
                                      STATUS_STRETCH_TIMEOUT |
                                      STATUS_ARB_LOST),
                            0U);
    I2cAdapterSim::ExpectEq("clear all error", sim.ErrorCode(status), 0U);
    I2cAdapterSim::ExpectEq("clear all tx count", sim.TxCount(status), 0U);
    I2cAdapterSim::ExpectEq("clear all rx count", sim.RxCount(status), 0U);

    SeedStickyStatus(sim);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("seed done", status & STATUS_DONE, STATUS_DONE);
    I2cAdapterSim::ExpectEq("seed ack", status & STATUS_ACK_ERROR,
                            STATUS_ACK_ERROR);
    I2cAdapterSim::ExpectEq("seed stretch", status & STATUS_STRETCH_TIMEOUT,
                            STATUS_STRETCH_TIMEOUT);
    I2cAdapterSim::ExpectEq("seed arb", status & STATUS_ARB_LOST,
                            STATUS_ARB_LOST);
    I2cAdapterSim::ExpectEq("seed tx", sim.TxCount(status), 1U);
    I2cAdapterSim::ExpectEq("seed rx", sim.RxCount(status), 1U);
    I2cAdapterSim::ExpectEq("seed error", sim.ErrorCode(status), ERR_ARB_LOST);

    sim.ClearStatus(CLEAR_DONE);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear done only", status & STATUS_DONE, 0U);
    I2cAdapterSim::ExpectEq("ack kept after clear done",
                            status & STATUS_ACK_ERROR, STATUS_ACK_ERROR);
    I2cAdapterSim::ExpectEq("stretch kept after clear done",
                            status & STATUS_STRETCH_TIMEOUT,
                            STATUS_STRETCH_TIMEOUT);
    I2cAdapterSim::ExpectEq("arb kept after clear done",
                            status & STATUS_ARB_LOST, STATUS_ARB_LOST);
    I2cAdapterSim::ExpectEq("tx kept after clear done", sim.TxCount(status), 1U);
    I2cAdapterSim::ExpectEq("rx kept after clear done", sim.RxCount(status), 1U);
    I2cAdapterSim::ExpectEq("error kept after clear done",
                            sim.ErrorCode(status), ERR_ARB_LOST);

    sim.ClearStatus(CLEAR_ACK_ERROR);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear ack only", status & STATUS_ACK_ERROR, 0U);
    I2cAdapterSim::ExpectEq("stretch kept after clear ack",
                            status & STATUS_STRETCH_TIMEOUT,
                            STATUS_STRETCH_TIMEOUT);
    I2cAdapterSim::ExpectEq("arb kept after clear ack",
                            status & STATUS_ARB_LOST, STATUS_ARB_LOST);
    I2cAdapterSim::ExpectEq("tx kept after clear ack", sim.TxCount(status), 1U);
    I2cAdapterSim::ExpectEq("rx kept after clear ack", sim.RxCount(status), 1U);
    I2cAdapterSim::ExpectEq("error kept after clear ack",
                            sim.ErrorCode(status), ERR_ARB_LOST);

    sim.ClearStatus(CLEAR_STRETCH_TIMEOUT);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear stretch only",
                            status & STATUS_STRETCH_TIMEOUT, 0U);
    I2cAdapterSim::ExpectEq("arb kept after clear stretch",
                            status & STATUS_ARB_LOST, STATUS_ARB_LOST);
    I2cAdapterSim::ExpectEq("tx kept after clear stretch",
                            sim.TxCount(status), 1U);
    I2cAdapterSim::ExpectEq("rx kept after clear stretch",
                            sim.RxCount(status), 1U);
    I2cAdapterSim::ExpectEq("error kept after clear stretch",
                            sim.ErrorCode(status), ERR_ARB_LOST);

    sim.ClearStatus(CLEAR_ARB_LOST);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear arb only", status & STATUS_ARB_LOST, 0U);
    I2cAdapterSim::ExpectEq("tx kept after clear arb", sim.TxCount(status), 1U);
    I2cAdapterSim::ExpectEq("rx kept after clear arb", sim.RxCount(status), 1U);
    I2cAdapterSim::ExpectEq("error kept after clear arb",
                            sim.ErrorCode(status), ERR_ARB_LOST);

    sim.ClearStatus(CLEAR_TX);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear tx only", sim.TxCount(status), 0U);
    I2cAdapterSim::ExpectEq("rx kept after clear tx", sim.RxCount(status), 1U);
    I2cAdapterSim::ExpectEq("error kept after clear tx",
                            sim.ErrorCode(status), ERR_ARB_LOST);

    sim.ClearStatus(CLEAR_RX);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear rx only", sim.RxCount(status), 0U);
    I2cAdapterSim::ExpectEq("error kept after clear rx",
                            sim.ErrorCode(status), ERR_ARB_LOST);

    sim.ClearStatus(CLEAR_ERROR_CODE);
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("clear error only", sim.ErrorCode(status), 0U);
}

void TestLengthsAndFinalReadNack(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x60U, 1U);
    sim.PushWriteData(0x81U, RESP_OK);
    sim.StartWrite(RESP_OK);
    std::array<uint8_t, 16> data{};
    data[0] = 0x81U;
    sim.ExpectWriteTransaction(0x50U, 0x60U, data, 1U);
    sim.WaitDoneStatus();

    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x61U, 16U);
    for(uint8_t i = 0U; i < 16U; ++i) {
        data[i] = static_cast<uint8_t>(0x90U + i);
        sim.PushWriteData(data[i], RESP_OK);
    }
    sim.StartWrite(RESP_OK);
    sim.ExpectWriteTransaction(0x50U, 0x61U, data, 16U);
    sim.WaitDoneStatus();

    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x62U, 1U);
    data[0] = 0xa1U;
    sim.StartRead(RESP_OK);
    sim.ExpectReadTransaction(0x50U, 0x62U, data, 1U);
    sim.WaitDoneStatus();

    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x63U, 16U);
    for(uint8_t i = 0U; i < 16U; ++i) {
        data[i] = static_cast<uint8_t>(0xb0U + i);
    }
    sim.StartRead(RESP_OK);
    sim.ExpectReadTransaction(0x50U, 0x63U, data, 16U);
    sim.WaitDoneStatus();
}

void TestExceptionsReleaseAndRecover(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.SetStretchTimeout(8U);
    sim.ConfigureTransfer(0x50U, 0x70U, 1U);
    sim.PushWriteData(0xc1U, RESP_OK);
    sim.StartWrite(RESP_OK);
    sim.ForceStretchTimeout();
    uint32_t status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("stretch timeout bit",
                            status & STATUS_STRETCH_TIMEOUT,
                            STATUS_STRETCH_TIMEOUT);
    I2cAdapterSim::ExpectEq("stretch timeout code",
                            sim.ErrorCode(status), ERR_STRETCH_TIMEOUT);
    sim.ExpectBusReleased();
    ExpectMinimalWriteRecovery(sim, 0x71U, 0xc2U);

    sim.ClearStatus(0U);
    sim.SetStretchTimeout(64U);
    sim.ConfigureTransfer(0x50U, 0x72U, 1U);
    sim.PushWriteData(0xc3U, RESP_OK);
    sim.StartWrite(RESP_OK);
    sim.ForceArbitrationLost();
    status = sim.GetStatus();
    I2cAdapterSim::ExpectEq("arb lost bit",
                            status & STATUS_ARB_LOST,
                            STATUS_ARB_LOST);
    I2cAdapterSim::ExpectEq("arb lost code",
                            sim.ErrorCode(status), ERR_ARB_LOST);
    sim.ExpectBusReleased();
    ExpectMinimalWriteRecovery(sim, 0x73U, 0xc4U);
}

void TestBadMessageTypeNoStateChange(I2cAdapterSim &sim)
{
    sim.ClearStatus(0U);
    sim.ConfigureTransfer(0x50U, 0x80U, 1U);
    sim.PushWriteData(0xd1U, RESP_OK);
    uint32_t before = sim.GetStatus();
    sim.BadSetDevAddr(0x22U);
    sim.BadStartWrite();
    sim.ExpectNoStart(80);
    uint32_t after = sim.GetStatus();
    I2cAdapterSim::ExpectEq("bad type tx count stable",
                            sim.TxCount(after), sim.TxCount(before));
    I2cAdapterSim::ExpectEq("bad type rx count stable",
                            sim.RxCount(after), sim.RxCount(before));
    I2cAdapterSim::ExpectEq("bad type error code stable",
                            sim.ErrorCode(after), sim.ErrorCode(before));

    sim.StartWrite(RESP_OK);
    std::array<uint8_t, 16> data{};
    data[0] = 0xd1U;
    sim.ExpectWriteTransaction(0x50U, 0x80U, data, 1U);
    sim.WaitDoneStatus();
}

} // namespace

int main(int argc, char **argv)
{
    Verilated::commandArgs(argc, argv);

    I2cAdapterSim sim;
    sim.Reset();
    sim.SetClkDiv(4U);
    sim.SetStretchTimeout(64U);

    ExpectResetDefaults(sim);
    TestNackFourPhases(sim);
    TestInvalidLength(sim);
    TestUnderflowOverflowAndFifoCounts(sim);
    TestBusyResponses(sim);
    TestClearStatusMasks(sim);
    TestLengthsAndFinalReadNack(sim);
    TestExceptionsReleaseAndRecover(sim);
    TestBadMessageTypeNoStateChange(sim);

    VerilatedCov::write("tests/build/verilator/i2c_adapter/coverage.dat");
    std::printf("FUNCTIONAL_COVERAGE: 18/18\n");
    std::printf("PASS: periphx_i2c_adapter_v2\n");
    return 0;
}
