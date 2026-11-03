// The Orb — ES3C28P (ESP32-S3R8, 8MB OPI PSRAM, 16MB QSPI flash)
// Native USB-Serial-JTAG is the REPL console (board has no separate USB-UART chip).
#define MICROPY_HW_BOARD_NAME               "The Orb ES3C28P"
#define MICROPY_HW_MCU_NAME                 "ESP32-S3"

// No external USB-UART: REPL over the native USB-Serial-JTAG peripheral.
// (Do NOT define MICROPY_HW_ENABLE_UART_REPL.)

// Default board I2C (touch FT6336G @ 0x38, codec ES8311 @ 0x18)
#define MICROPY_HW_I2C0_SCL                 (15)
#define MICROPY_HW_I2C0_SDA                 (16)

// Main SPI bus (radio / expansion): SCK=14 MOSI=3 MISO=2 SS=21
#define MICROPY_HW_SPI1_SCK                 (14)
#define MICROPY_HW_SPI1_MOSI                (3)
#define MICROPY_HW_SPI1_MISO                (2)
