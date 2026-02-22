"""
BLE UART Service for Heltec V3.1
"""

import bluetooth
import struct
from micropython import const

_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)


class BleUart:
    def __init__(self, name="HeronSquawk", rx_callback=None):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq_handler)
        self._name = name
        self._rx_callback = rx_callback
        self._conn_handle = None
        self._tx_handle = None
        self._rx_handle = None
        self._rx_buffer = bytearray()
        self._connected = False
        self._mtu = 20
        self._register_services()

    def _register_services(self):
        svc = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
        tx = bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
        rx = bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e")
        NUS = (svc, ((tx, _FLAG_READ | _FLAG_NOTIFY), (rx, _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE)))
        ((self._tx_handle, self._rx_handle),) = self._ble.gatts_register_services((NUS,))
        self._ble.gatts_write(self._tx_handle, b'')

    def _irq_handler(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, addr_type, addr = data
            self._conn_handle = conn_handle
            self._connected = True
            # Stop advertising once connected to save resources
            self.stop_advertising()
            print("BLE: Connected")
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, addr_type, addr = data
            self._conn_handle = None
            self._connected = False
            print("BLE: Disconnected")
            self.start_advertising()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, attr_handle = data
            if attr_handle == self._rx_handle:
                value = self._ble.gatts_read(self._rx_handle)
                self._handle_rx(value)

    def _handle_rx(self, data):
        # Safety: clear buffer if it gets too large (stale data without newline)
        if len(self._rx_buffer) > 512:
            print("BLE: Clearing stale buffer")
            self._rx_buffer = bytearray()

        self._rx_buffer.extend(data)
        while b'\n' in self._rx_buffer:
            idx = self._rx_buffer.index(b'\n')
            line = bytes(self._rx_buffer[:idx])
            self._rx_buffer = self._rx_buffer[idx+1:]
            if line.endswith(b'\r'):
                line = line[:-1]
            if line and self._rx_callback:
                try:
                    self._rx_callback(line.decode('utf-8'))
                except Exception as e:
                    print("BLE RX error:", e)

    def _make_adv_payload(self, name=None):
        payload = bytearray()
        payload += struct.pack("BBB", 2, _ADV_TYPE_FLAGS, 0x06)
        if name:
            n = name.encode()[:8]
            payload += struct.pack("BB", len(n) + 1, _ADV_TYPE_NAME) + n
        return payload

    def start_advertising(self, interval_us=100000):
        payload = self._make_adv_payload(name=self._name)
        self._ble.gap_advertise(interval_us, adv_data=payload)
        print("BLE: Advertising as", self._name)

    def stop_advertising(self):
        self._ble.gap_advertise(None)

    def is_connected(self):
        return self._connected

    def send(self, data):
        if not self._connected or self._conn_handle is None:
            return False
        if isinstance(data, str):
            data = data.encode('utf-8')
        if not data.endswith(b'\n'):
            data = data + b'\n'
        chunk_size = self._mtu - 3
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            self._ble.gatts_notify(self._conn_handle, self._tx_handle, chunk)
        return True

    def disconnect(self):
        if self._conn_handle is not None:
            self._ble.gap_disconnect(self._conn_handle)

    def set_callback(self, callback):
        self._rx_callback = callback


_ble_uart = None

def get_ble_uart(name=None, rx_callback=None):
    global _ble_uart
    if _ble_uart is None:
        _ble_uart = BleUart(name=name or "HeronSquawk", rx_callback=rx_callback)
    elif rx_callback is not None:
        _ble_uart.set_callback(rx_callback)
    return _ble_uart
