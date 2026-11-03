include(boards/mpconfigboard_esp32s3_common.cmake)

# NOTE: deliberately NOT including boards/sdkconfig.flash_qio_80m — that forces
# QIO flash which hangs on some ES3C28P flash chips. We use the ESP-IDF default
# flash mode (DIO) for maximum compatibility; bootloader is also flashed DIO.
list(APPEND SDKCONFIG_DEFAULTS
    boards/sdkconfig.240mhz
    boards/sdkconfig.spiram_oct
    ${MICROPY_BOARD_DIR}/sdkconfig.board
)

list(APPEND MICROPY_DEF_BOARD
    MICROPY_HW_BOARD_NAME="The Orb ES3C28P"
)
