"""
SX1262 LoRa Driver for Heltec V3.1
Based on micropySX126X library

Heltec V3.1 Pin Mapping:
  SCK  = 9
  MOSI = 10
  MISO = 11
  CS   = 8
  IRQ  = 14 (DIO1)
  RST  = 12
  BUSY = 13
"""

from _sx126x import *
from sx126x import SX126X

_SX126X_PA_CONFIG_SX1262 = const(0x00)

# Export bandwidth constants for easy use
BW_125 = 125.0
BW_250 = 250.0
BW_500 = 500.0

# Export coding rate constants
CR_4_5 = 5
CR_4_6 = 6
CR_4_7 = 7
CR_4_8 = 8

# Heltec V3.1 default pins
HELTEC_V3_SPI_BUS = 1
HELTEC_V3_CLK = 9
HELTEC_V3_MOSI = 10
HELTEC_V3_MISO = 11
HELTEC_V3_CS = 8
HELTEC_V3_IRQ = 14
HELTEC_V3_RST = 12
HELTEC_V3_BUSY = 13


class SX1262(SX126X):
    """SX1262 driver with Heltec V3.1 default pins"""

    TX_DONE = SX126X_IRQ_TX_DONE
    RX_DONE = SX126X_IRQ_RX_DONE
    ADDR_FILT_OFF = SX126X_GFSK_ADDRESS_FILT_OFF
    ADDR_FILT_NODE = SX126X_GFSK_ADDRESS_FILT_NODE
    ADDR_FILT_NODE_BROAD = SX126X_GFSK_ADDRESS_FILT_NODE_BROADCAST
    PREAMBLE_DETECT_OFF = SX126X_GFSK_PREAMBLE_DETECT_OFF
    PREAMBLE_DETECT_8 = SX126X_GFSK_PREAMBLE_DETECT_8
    PREAMBLE_DETECT_16 = SX126X_GFSK_PREAMBLE_DETECT_16
    PREAMBLE_DETECT_24 = SX126X_GFSK_PREAMBLE_DETECT_24
    PREAMBLE_DETECT_32 = SX126X_GFSK_PREAMBLE_DETECT_32
    STATUS = ERROR

    def __init__(self, spi_bus=HELTEC_V3_SPI_BUS, clk=HELTEC_V3_CLK, mosi=HELTEC_V3_MOSI,
                 miso=HELTEC_V3_MISO, cs=HELTEC_V3_CS, irq=HELTEC_V3_IRQ,
                 rst=HELTEC_V3_RST, gpio=HELTEC_V3_BUSY):
        """
        Initialize SX1262 with Heltec V3.1 pin defaults.

        For Heltec V3.1, just use: sx = SX1262()
        Or override pins: sx = SX1262(spi_bus=1, clk=9, mosi=10, miso=11, cs=8, irq=14, rst=12, gpio=13)
        """
        super().__init__(spi_bus, clk, mosi, miso, cs, irq, rst, gpio)
        self._callbackFunction = self._dummyFunction
        self.blocking = True

    def begin(self, freq=915.0, bw=125.0, sf=9, cr=5, syncWord=SX126X_SYNC_WORD_PRIVATE,
              power=14, currentLimit=60.0, preambleLength=8, implicit=False, implicitLen=0xFF,
              crcOn=True, txIq=False, rxIq=False, tcxoVoltage=1.7, useRegulatorLDO=False,
              blocking=True):
        """
        Initialize the SX1262 for LoRa mode.

        Parameters:
            freq: Frequency in MHz (e.g., 915.0 for 915MHz)
            bw: Bandwidth in kHz (125.0, 250.0, or 500.0)
            sf: Spreading factor (5-12)
            cr: Coding rate (5=4/5, 6=4/6, 7=4/7, 8=4/8)
            syncWord: Sync word (0x12=private, 0x34=public)
            power: TX power in dBm (-9 to 22)
            currentLimit: OCP limit in mA
            preambleLength: Preamble length in symbols
            implicit: Use implicit header mode
            implicitLen: Implicit header payload length
            crcOn: Enable CRC
            txIq: Invert TX IQ
            rxIq: Invert RX IQ
            tcxoVoltage: TCXO voltage (1.6 or 1.7 for Heltec V3)
            useRegulatorLDO: Use LDO instead of DC-DC
            blocking: Use blocking mode for TX/RX
        """
        state = super().begin(bw, sf, cr, syncWord, currentLimit, preambleLength,
                              tcxoVoltage, useRegulatorLDO, txIq, rxIq)
        ASSERT(state)

        if not implicit:
            state = super().explicitHeader()
        else:
            state = super().implicitHeader(implicitLen)
        ASSERT(state)

        state = super().setCRC(crcOn)
        ASSERT(state)

        state = self.setFrequency(freq)
        ASSERT(state)

        state = self.setOutputPower(power)
        ASSERT(state)

        state = super().fixPaClamping()
        ASSERT(state)

        state = self.setBlockingCallback(blocking)

        return state

    def setFrequency(self, freq, calibrate=True):
        """
        Set frequency in MHz.

        Parameters:
            freq: Frequency in MHz (150-960)
            calibrate: Perform image calibration
        """
        if freq < 150.0 or freq > 960.0:
            return ERR_INVALID_FREQUENCY

        state = ERR_NONE

        if calibrate:
            data = bytearray(2)
            if freq > 900.0:
                data[0] = SX126X_CAL_IMG_902_MHZ_1
                data[1] = SX126X_CAL_IMG_902_MHZ_2
            elif freq > 850.0:
                data[0] = SX126X_CAL_IMG_863_MHZ_1
                data[1] = SX126X_CAL_IMG_863_MHZ_2
            elif freq > 770.0:
                data[0] = SX126X_CAL_IMG_779_MHZ_1
                data[1] = SX126X_CAL_IMG_779_MHZ_2
            elif freq > 460.0:
                data[0] = SX126X_CAL_IMG_470_MHZ_1
                data[1] = SX126X_CAL_IMG_470_MHZ_2
            else:
                data[0] = SX126X_CAL_IMG_430_MHZ_1
                data[1] = SX126X_CAL_IMG_430_MHZ_2
            state = super().calibrateImage(data)
            ASSERT(state)

        return super().setFrequencyRaw(freq)

    def setOutputPower(self, power):
        """
        Set TX output power in dBm.

        Parameters:
            power: Power in dBm (-9 to 22)
        """
        if not ((power >= -9) and (power <= 22)):
            return ERR_INVALID_OUTPUT_POWER

        ocp = bytearray(1)
        ocp_mv = memoryview(ocp)
        state = super().readRegister(SX126X_REG_OCP_CONFIGURATION, ocp_mv, 1)
        ASSERT(state)

        state = super().setPaConfig(0x04, _SX126X_PA_CONFIG_SX1262)
        ASSERT(state)

        state = super().setTxParams(power)
        ASSERT(state)

        return super().writeRegister(SX126X_REG_OCP_CONFIGURATION, ocp, 1)

    def setTxIq(self, txIq):
        """Set TX IQ inversion"""
        self._txIq = txIq

    def startReceive(self, timeout=None):
        """Put radio in receive mode"""
        if timeout is None:
            return super().startReceive()
        return super().startReceive(timeout)

    def setRxIq(self, rxIq):
        """Set RX IQ inversion"""
        self._rxIq = rxIq
        if not self.blocking:
            ASSERT(super().startReceive())

    def setPreambleDetectorLength(self, preambleDetectorLength):
        """Set preamble detector length"""
        self._preambleDetectorLength = preambleDetectorLength
        if not self.blocking:
            ASSERT(super().startReceive())

    def setBlockingCallback(self, blocking, callback=None):
        """
        Set blocking mode and optional callback.

        Parameters:
            blocking: True for blocking TX/RX, False for non-blocking
            callback: Callback function for non-blocking mode
        """
        self.blocking = blocking
        if not self.blocking:
            state = super().startReceive()
            ASSERT(state)
            if callback is not None:
                self._callbackFunction = callback
                super().setDio1Action(self._onIRQ)
            else:
                self._callbackFunction = self._dummyFunction
                super().clearDio1Action()
            return state
        else:
            state = super().standby()
            ASSERT(state)
            self._callbackFunction = self._dummyFunction
            super().clearDio1Action()
            return state

    def recv(self, len_=0, timeout_en=False, timeout_ms=0):
        """
        Receive data.

        Parameters:
            len_: Expected length (0 for variable)
            timeout_en: Enable timeout
            timeout_ms: Timeout in milliseconds

        Returns:
            (data, state) tuple
        """
        if not self.blocking:
            return self._readData(len_)
        else:
            return self._receive(len_, timeout_en, timeout_ms)

    def send(self, data):
        """
        Send data.

        Parameters:
            data: bytes or bytearray to send

        Returns:
            (length_sent, state) tuple
        """
        if not self.blocking:
            return self._startTransmit(data)
        else:
            return self._transmit(data)

    def _events(self):
        """Get IRQ events"""
        return super().getIrqStatus()

    def _receive(self, len_=0, timeout_en=False, timeout_ms=0):
        """Blocking receive"""
        state = ERR_NONE

        length = len_
        if len_ == 0:
            length = SX126X_MAX_PACKET_LENGTH

        data = bytearray(length)
        data_mv = memoryview(data)

        try:
            state = super().receive(data_mv, length, timeout_en, timeout_ms)
        except AssertionError as e:
            state = list(ERROR.keys())[list(ERROR.values()).index(str(e))]

        if state == ERR_NONE or state == ERR_CRC_MISMATCH:
            if len_ == 0:
                length = super().getPacketLength(False)
                data = data[:length]
        else:
            return b'', state

        return bytes(data), state

    def _transmit(self, data):
        """Blocking transmit"""
        if isinstance(data, bytes) or isinstance(data, bytearray):
            pass
        else:
            return 0, ERR_INVALID_PACKET_TYPE

        state = super().transmit(data, len(data))
        return len(data), state

    def _readData(self, len_=0):
        """Non-blocking read"""
        state = ERR_NONE

        length = super().getPacketLength()

        if len_ < length and len_ != 0:
            length = len_

        data = bytearray(length)
        data_mv = memoryview(data)

        try:
            state = super().readData(data_mv, length)
        except AssertionError as e:
            state = list(ERROR.keys())[list(ERROR.values()).index(str(e))]

        ASSERT(super().startReceive())

        if state == ERR_NONE or state == ERR_CRC_MISMATCH:
            return bytes(data), state
        else:
            return b'', state

    def _startTransmit(self, data):
        """Non-blocking transmit"""
        if isinstance(data, bytes) or isinstance(data, bytearray):
            pass
        else:
            return 0, ERR_INVALID_PACKET_TYPE

        state = super().startTransmit(data, len(data))
        return len(data), state

    def _dummyFunction(self, *args):
        """Placeholder callback"""
        pass

    def _onIRQ(self, callback):
        """IRQ handler"""
        events = self._events()
        if events & SX126X_IRQ_TX_DONE:
            super().startReceive()
        self._callbackFunction(events)