#include "stm32f10x.h"
#include "delay.h"
#include "periphx_sdk.h"

/*
 * Kept for compatibility with the template IRQ file.
 * The initial debug flow does not use SPI RX interrupts.
 */
volatile uint8_t spi1_rx_byte = 0;
volatile uint8_t spi1_rx_flag = 0;

typedef struct {
    SPI_TypeDef *spi;
    GPIO_TypeDef *cs_port;
    uint16_t cs_pin;
} periphx_stm32f1_ctx_t;

static periphx_stm32f1_ctx_t g_periphx_ctx = {
    .spi = SPI1,
    .cs_port = GPIOA,
    .cs_pin = GPIO_Pin_4,
};

static periphx_device_t g_periphx_dev;

#define PERIPHX_SPI_TIMEOUT_LOOPS 1000000u
#define PWM_CARRIER_PERIOD        50000u
#define PWM_BREATH_STEP           250u
#define PWM_BREATH_DELAY_MS       5u

static void PeriphX_CS_High(void)
{
    GPIO_SetBits(g_periphx_ctx.cs_port, g_periphx_ctx.cs_pin);
}

static void PeriphX_CS_Low(void)
{
    GPIO_ResetBits(g_periphx_ctx.cs_port, g_periphx_ctx.cs_pin);
}

static int PeriphX_WaitFlagSet(SPI_TypeDef *spi, uint16_t flag)
{
    uint32_t timeout = PERIPHX_SPI_TIMEOUT_LOOPS;
    while (SPI_I2S_GetFlagStatus(spi, flag) == RESET) {
        if (timeout-- == 0u) {
            return -1;
        }
    }
    return 0;
}

static int PeriphX_WaitFlagClear(SPI_TypeDef *spi, uint16_t flag)
{
    uint32_t timeout = PERIPHX_SPI_TIMEOUT_LOOPS;
    while (SPI_I2S_GetFlagStatus(spi, flag) == SET) {
        if (timeout-- == 0u) {
            return -1;
        }
    }
    return 0;
}

static void PeriphX_FatalHalt(void)
{
    while (1) {
    }
}

static void SPI1_Init_Master(void)
{
    GPIO_InitTypeDef gpio;
    SPI_InitTypeDef spi;

    RCC_APB2PeriphClockCmd(RCC_APB2Periph_SPI1 | RCC_APB2Periph_GPIOA | RCC_APB2Periph_AFIO, ENABLE);

    /* CS: manual GPIO control. */
    gpio.GPIO_Pin = GPIO_Pin_4;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOA, &gpio);
    PeriphX_CS_High();

    /* SCK and MOSI: SPI1 alternate function push-pull. */
    gpio.GPIO_Pin = GPIO_Pin_5 | GPIO_Pin_7;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOA, &gpio);

    /* MISO: input floating. */
    gpio.GPIO_Pin = GPIO_Pin_6;
    gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &gpio);

    SPI_I2S_DeInit(SPI1);
    SPI_StructInit(&spi);
    spi.SPI_Direction = SPI_Direction_2Lines_FullDuplex;
    spi.SPI_Mode = SPI_Mode_Master;
    spi.SPI_DataSize = SPI_DataSize_8b;
    spi.SPI_CPOL = SPI_CPOL_Low;
    spi.SPI_CPHA = SPI_CPHA_1Edge;
    spi.SPI_NSS = SPI_NSS_Soft;
    spi.SPI_BaudRatePrescaler = SPI_BaudRatePrescaler_256;
    spi.SPI_FirstBit = SPI_FirstBit_MSB;
    spi.SPI_CRCPolynomial = 7;
    SPI_Init(SPI1, &spi);
    SPI_NSSInternalSoftwareConfig(SPI1, SPI_NSSInternalSoft_Set);
    SPI_Cmd(SPI1, ENABLE);
}

static int PeriphX_Transfer(void *user, const uint8_t *tx, uint8_t *rx, size_t len)
{
    periphx_stm32f1_ctx_t *ctx = (periphx_stm32f1_ctx_t *)user;

    if (ctx == NULL || ctx->spi == NULL) {
        return PERIPHX_ERR_IO;
    }

    PeriphX_CS_Low();
    Delay_us(1);

    for (size_t i = 0; i < len; ++i) {
        if (PeriphX_WaitFlagSet(ctx->spi, SPI_I2S_FLAG_TXE) != 0) {
            PeriphX_CS_High();
            return PERIPHX_ERR_IO;
        }

        SPI_I2S_SendData(ctx->spi, tx ? tx[i] : 0xFFu);

        if (PeriphX_WaitFlagSet(ctx->spi, SPI_I2S_FLAG_RXNE) != 0) {
            PeriphX_CS_High();
            return PERIPHX_ERR_IO;
        }

        if (rx != NULL) {
            rx[i] = (uint8_t)SPI_I2S_ReceiveData(ctx->spi);
        } else {
            (void)SPI_I2S_ReceiveData(ctx->spi);
        }
    }

    if (PeriphX_WaitFlagClear(ctx->spi, SPI_I2S_FLAG_BSY) != 0) {
        PeriphX_CS_High();
        return PERIPHX_ERR_IO;
    }

    PeriphX_CS_High();
    return PERIPHX_OK;
}

static int PeriphX_ProgramPwm(uint32_t period, uint32_t duty, uint32_t *response_value)
{
    int status;
    uint32_t response = 0;

    status = periphx_pwm_led1_set_sys_cnt_prds(&g_periphx_dev, period, &response);
    if (status != PERIPHX_OK || response != period) {
        return PERIPHX_ERR_RESPONSE;
    }

    status = periphx_pwm_led1_set_sys_cnt_duty(&g_periphx_dev, duty, &response);
    if (status != PERIPHX_OK || response != duty) {
        return PERIPHX_ERR_RESPONSE;
    }

    status = periphx_pwm_led2_set_sys_cnt_prds(&g_periphx_dev, period, &response);
    if (status != PERIPHX_OK || response != period) {
        return PERIPHX_ERR_RESPONSE;
    }

    status = periphx_pwm_led2_set_sys_cnt_duty(&g_periphx_dev, duty, &response);
    if (status != PERIPHX_OK || response != duty) {
        return PERIPHX_ERR_RESPONSE;
    }

    if (response_value != NULL) {
        *response_value = response;
    }

    return PERIPHX_OK;
}

static void PeriphX_RunBreathingLoop(void)
{
    uint32_t response = 0;
    int status;

    for (;;) {
        for (uint32_t duty = 0u; duty <= PWM_CARRIER_PERIOD; duty += PWM_BREATH_STEP) {
            status = PeriphX_ProgramPwm(PWM_CARRIER_PERIOD, duty, &response);
            if (status != PERIPHX_OK) {
                /* PeriphX_FatalHalt(); */
            }
            Delay_ms(PWM_BREATH_DELAY_MS);
        }

        for (int32_t duty = (int32_t)PWM_CARRIER_PERIOD; duty >= 0; duty -= (int32_t)PWM_BREATH_STEP) {
            status = PeriphX_ProgramPwm(PWM_CARRIER_PERIOD, (uint32_t)duty, &response);
            if (status != PERIPHX_OK) {
                /* PeriphX_FatalHalt(); */
            }
            Delay_ms(PWM_BREATH_DELAY_MS);
        }
    }
}

int main(void)
{
    SPI1_Init_Master();
    periphx_device_init(&g_periphx_dev, PeriphX_Transfer, &g_periphx_ctx);

    Delay_ms(100);

    /* Start from a dark state so the breathing ramp is visible immediately. */
    (void)PeriphX_ProgramPwm(PWM_CARRIER_PERIOD, 0u, NULL);

    PeriphX_RunBreathingLoop();
    return 0;
}