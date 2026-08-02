#include "periphx_sdk.h"

static uint8_t crc4_step(uint8_t crc_in, uint8_t bit_in)
{
    uint8_t feedback = (uint8_t)(((crc_in >> 3) ^ bit_in) & 0x1u);
    uint8_t crc_out = (uint8_t)((crc_in << 1) & 0xFu);
    if(feedback) {
        crc_out ^= 0x3u;
    }
    return (uint8_t)(crc_out & 0xFu);
}

static uint8_t crc4_byte(uint8_t crc_in, uint8_t data)
{
    for(int bit = 7; bit >= 0; --bit) {
        crc_in = crc4_step(crc_in, (uint8_t)((data >> bit) & 0x1u));
    }
    return (uint8_t)(crc_in & 0xFu);
}

static uint8_t crc4_nibble(uint8_t crc_in, uint8_t data)
{
    for(int bit = 3; bit >= 0; --bit) {
        crc_in = crc4_step(crc_in, (uint8_t)((data >> bit) & 0x1u));
    }
    return (uint8_t)(crc_in & 0xFu);
}

static uint8_t crc4_frame(const periphx_frame_t *frame)
{
    uint8_t crc = 0u;
    crc = crc4_byte(crc, frame->server_id);
    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 24));
    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 16));
    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 8));
    crc = crc4_byte(crc, (uint8_t)frame->payload);
    crc = crc4_nibble(crc, frame->msg_type);
    return (uint8_t)(crc & 0xFu);
}

static void pack_frame(const periphx_frame_t *frame, uint8_t bytes[PERIPHX_FRAME_LEN])
{
    bytes[0] = frame->server_id;
    bytes[1] = (uint8_t)(frame->payload >> 24);
    bytes[2] = (uint8_t)(frame->payload >> 16);
    bytes[3] = (uint8_t)(frame->payload >> 8);
    bytes[4] = (uint8_t)frame->payload;
    bytes[5] = (uint8_t)(((frame->crc4 & 0xFu) << 4) | (frame->msg_type & 0xFu));
}

static void unpack_frame(periphx_frame_t *frame, const uint8_t bytes[PERIPHX_FRAME_LEN])
{
    frame->server_id = bytes[0];
    frame->payload = ((uint32_t)bytes[1] << 24) | ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 8) | (uint32_t)bytes[4];
    frame->msg_type = (uint8_t)(bytes[5] & 0xFu);
    frame->crc4 = (uint8_t)((bytes[5] >> 4) & 0xFu);
}

void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user)
{
    dev->transfer = transfer;
    dev->user = user;
}

static int transfer_bytes(periphx_device_t *dev, const uint8_t *tx_bytes, uint8_t *rx_bytes, size_t len)
{
    if(dev->transfer == NULL) {
        return PERIPHX_ERR_IO;
    }
    if(dev->transfer(dev->user, tx_bytes, rx_bytes, len) != 0) {
        return PERIPHX_ERR_IO;
    }
    return PERIPHX_OK;
}

int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response)
{
    uint8_t tx_bytes[PERIPHX_TRANSACTION_LEN];
    uint8_t rx_bytes[PERIPHX_TRANSACTION_LEN];
    periphx_frame_t tmp = *request;
    tmp.msg_type &= 0xFu;
    tmp.crc4 = crc4_frame(&tmp);
    pack_frame(&tmp, tx_bytes);
    #if PERIPHX_DEBUG_DEFERRED_READBACK
    for(size_t i = 0; i < PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN; ++i) {
        tx_bytes[PERIPHX_FRAME_LEN + i] = PERIPHX_DEBUG_READBACK_TOKEN;
    }
    #else
    for(size_t i = 0; i < PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN; ++i) {
        tx_bytes[PERIPHX_FRAME_LEN + i] = 0xFFu;
    }
    #endif
    /*
     * One SPI transaction carries the request plus three turnaround bytes
     * and then a readback window:
     *   - bytes 0..5  : the actual request
     *   - bytes 6..8  : turnaround / alignment bytes
     *   - bytes 8..13 : the deferred response
     * The extra turnaround bytes are intentional during bring-up because the
     * FPGA prototype only presents the response after the request frame has
     * fully drained through the router path.
     */
    if(transfer_bytes(dev, tx_bytes, rx_bytes, PERIPHX_TRANSACTION_LEN) != PERIPHX_OK) {
        return PERIPHX_ERR_IO;
    }
    unpack_frame(response, rx_bytes + PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN);
    if(crc4_frame(response) != response->crc4) {
        return PERIPHX_ERR_CRC;
    }
    if(response->server_id != request->server_id) {
        return PERIPHX_ERR_RESPONSE;
    }
    return PERIPHX_OK;
}

int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value)
{
    periphx_frame_t request = { service_id, value, PERIPHX_MSG_REQUEST, 0u };
    periphx_frame_t response = {0};
    int status = periphx_transfer_frame(dev, &request, &response);
    if(status != PERIPHX_OK) {
        return status;
    }
    if(response.msg_type == PERIPHX_MSG_ERROR) {
        return PERIPHX_ERR_RESPONSE;
    }
    if(response.msg_type != PERIPHX_MSG_RESPONSE) {
        return PERIPHX_ERR_RESPONSE;
    }
    if(response_value != NULL) {
        *response_value = response.payload;
    }
    return PERIPHX_OK;
}

int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value)
{
    return periphx_call_u32(dev, service_id, (uint32_t)value, response_value);
}

int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value)
{
    return periphx_call_u32(dev, service_id, value ? 1u : 0u, response_value);
}

int periphx_pwm_led1_set_sys_cnt_prds(periphx_device_t *dev, uint32_t value, uint32_t *response_value)
{
    return periphx_call_u32(dev, PERIPHX_PWM_LED1_SET_SYS_CNT_PRDS_ID, value, response_value);
}

int periphx_pwm_led1_set_sys_cnt_duty(periphx_device_t *dev, uint32_t value, uint32_t *response_value)
{
    return periphx_call_u32(dev, PERIPHX_PWM_LED1_SET_SYS_CNT_DUTY_ID, value, response_value);
}

int periphx_pwm_led2_set_sys_cnt_prds(periphx_device_t *dev, uint32_t value, uint32_t *response_value)
{
    return periphx_call_u32(dev, PERIPHX_PWM_LED2_SET_SYS_CNT_PRDS_ID, value, response_value);
}

int periphx_pwm_led2_set_sys_cnt_duty(periphx_device_t *dev, uint32_t value, uint32_t *response_value)
{
    return periphx_call_u32(dev, PERIPHX_PWM_LED2_SET_SYS_CNT_DUTY_ID, value, response_value);
}

