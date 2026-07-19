#ifndef PERIPHX_SDK_H
#define PERIPHX_SDK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PERIPHX_FRAME_LEN 6u
#define PERIPHX_TURNAROUND_LEN 3u
#define PERIPHX_TRANSACTION_LEN (PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN)
#define PERIPHX_MSG_REQUEST 0x0u
#define PERIPHX_MSG_RESPONSE 0x1u
#define PERIPHX_MSG_EVENT 0x2u
#define PERIPHX_MSG_ERROR 0x3u

/*
 * Temporary bring-up bridge:
 * The current FPGA prototype emits the response only after the request
 * frame has fully drained through the router path. A three-byte turnaround
 * window keeps the response aligned to a clean byte boundary, so the SDK
 * keeps CS low and clocks a request window, three turnaround bytes, and a
 * readback window in the same SPI transaction.
 * Once the hardware contract is frozen, this can be collapsed back to a
 * single helper in one place.
 */
#define PERIPHX_DEBUG_DEFERRED_READBACK 1u
#define PERIPHX_DEBUG_READBACK_TOKEN 0xFFu

typedef enum {
    PERIPHX_OK = 0,
    PERIPHX_ERR_IO = -1,
    PERIPHX_ERR_FRAME = -2,
    PERIPHX_ERR_CRC = -3,
    PERIPHX_ERR_RESPONSE = -4,
} periphx_status_t;

typedef int (*periphx_transport_fn)(void *user, const uint8_t *tx, uint8_t *rx, size_t len);

typedef struct {
    periphx_transport_fn transfer;
    void *user;
} periphx_device_t;

typedef struct {
    uint8_t server_id;
    uint32_t payload;
    uint8_t msg_type;
    uint8_t crc4;
} periphx_frame_t;

#define PERIPHX_PWM_LED1_SET_SYS_CNT_PRDS_ID 0u
#define PERIPHX_PWM_LED1_SET_SYS_CNT_DUTY_ID 1u
#define PERIPHX_PWM_LED2_SET_SYS_CNT_PRDS_ID 2u
#define PERIPHX_PWM_LED2_SET_SYS_CNT_DUTY_ID 3u

void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user);
int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response);
int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value);
int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value);
int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value);

int periphx_pwm_led1_set_sys_cnt_prds(periphx_device_t *dev, uint32_t value, uint32_t *response_value);
int periphx_pwm_led1_set_sys_cnt_duty(periphx_device_t *dev, uint32_t value, uint32_t *response_value);
int periphx_pwm_led2_set_sys_cnt_prds(periphx_device_t *dev, uint32_t value, uint32_t *response_value);
int periphx_pwm_led2_set_sys_cnt_duty(periphx_device_t *dev, uint32_t value, uint32_t *response_value);

#endif /* PERIPHX_SDK_H */
