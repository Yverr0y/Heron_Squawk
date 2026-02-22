import serial
import time
import threading
import logging
import os

# Set up logging for RYLR999 module
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'heronsquawk_debug.log')
logger = logging.getLogger('rylr999')

class RYLR999:
    def __init__(self, port, baud=115200, address=None):
        self.port = port
        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
        time.sleep(0.5)

        self._lock = threading.Lock()

        if not self._test_connection():
            raise Exception(f"No response from module on {port}")

        if address is not None:
            self.set_address(address)

        self.on_receive = None
        self._listening = False
        self._listener_thread = None

    def _send_command(self, cmd):
        with self._lock:
            self.ser.reset_input_buffer()
            self.ser.write((cmd + '\r\n').encode())
            time.sleep(0.5)
            response = ''
            while self.ser.in_waiting:
                response += self.ser.read(self.ser.in_waiting).decode()
                time.sleep(0.05)
            return response.strip()

    def _test_connection(self):
        response = self._send_command('AT')
        return '+OK' in response

    def set_address(self, address):
        response = self._send_command(f'AT+ADDRESS={address}')
        return '+OK' in response

    def get_address(self):
        response = self._send_command('AT+ADDRESS?')
        if '+ADDRESS=' in response:
            return int(response.split('=')[1])
        return None

    def set_frequency(self, freq_hz, save=False):
        if save:
            response = self._send_command(f'AT+BAND={freq_hz},M')
        else:
            response = self._send_command(f'AT+BAND={freq_hz}')
        return '+OK' in response

    def get_frequency(self):
        response = self._send_command('AT+BAND?')
        if '+BAND=' in response:
            return int(response.split('=')[1])
        return None

    def set_network_id(self, net_id):
        response = self._send_command(f'AT+NETWORKID={net_id}')
        return '+OK' in response

    def get_network_id(self):
        response = self._send_command('AT+NETWORKID?')
        if '+NETWORKID=' in response:
            return int(response.split('=')[1])
        return None

    def set_power(self, power_dbm):
        response = self._send_command(f'AT+CRFOP={power_dbm}')
        return '+OK' in response

    def get_power(self):
        response = self._send_command('AT+CRFOP?')
        if '+CRFOP=' in response:
            return int(response.split('=')[1])
        return None

    def set_parameters(self, sf=9, bw=7, cr=1, preamble=12):
        response = self._send_command(f'AT+PARAMETER={sf},{bw},{cr},{preamble}')
        return '+OK' in response

    def get_parameters(self):
        response = self._send_command('AT+PARAMETER?')
        if '+PARAMETER=' in response:
            parts = response.split('=')[1].split(',')
            return {
                'spreading_factor': int(parts[0]),
                'bandwidth': int(parts[1]),
                'coding_rate': int(parts[2]),
                'preamble': int(parts[3])
            }
        return None

    def get_config(self):
        return {
            'port': self.port,
            'address': self.get_address(),
            'network_id': self.get_network_id(),
            'frequency': self.get_frequency(),
            'power': self.get_power(),
            'parameters': self.get_parameters()
        }

    def reset(self):
        response = self._send_command('AT+RESET')
        time.sleep(1)
        return '+READY' in response

    def factory_reset(self):
        response = self._send_command('AT+FACTORY')
        return '+FACTORY' in response

    def get_temperature(self):
        response = self._send_command('AT+TEMP?')
        if '+TEMP=' in response:
            return float(response.split('=')[1])
        return None

    def get_version(self):
        response = self._send_command('AT+VER?')
        if '+VER=' in response:
            return response.split('=')[1]
        return None

    def send(self, dest_address, data):
        length = len(data)
        if length > 240:
            raise ValueError("Data exceeds 240 byte limit")
        cmd = f'AT+SEND={dest_address},{length},{data}'

        with self._lock:
            self.ser.reset_input_buffer()
            self.ser.write((cmd + '\r\n').encode())
            time.sleep(2.0)  # Wait for LoRa transmission to complete
            response = ''
            while self.ser.in_waiting:
                response += self.ser.read(self.ser.in_waiting).decode()
                time.sleep(0.05)
            response = response.strip()

        return '+OK' in response

    def send_bytes(self, dest_address, data_bytes):
        hex_str = data_bytes.hex().upper()
        return self.send(dest_address, hex_str)

    def start_listening(self, callback):
        self.on_receive = callback
        self._listening = True
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()

    def stop_listening(self):
        self._listening = False
        if self._listener_thread:
            self._listener_thread.join(timeout=2)

    def _listen_loop(self):
        buffer = ''
        print("[RYLR999] Listener thread started", flush=True)
        logger.info("RYLR999 listener thread started")
        loop_count = 0
        while self._listening:
            loop_count += 1
            if loop_count % 200 == 0:  # Log every 10 seconds (200 * 0.05s)
                print(f"[RYLR999] Listener alive, loops={loop_count}", flush=True)
                logger.debug(f"Listener alive, loops={loop_count}, buffer_len={len(buffer)}")
            # Read serial data while holding lock
            lines_to_process = []
            if self._lock.acquire(blocking=False):
                try:
                    if self.ser.in_waiting:
                        chunk = self.ser.read(self.ser.in_waiting).decode()
                        buffer += chunk
                        print(f"[RYLR999] Serial chunk: {len(chunk)} bytes", flush=True)
                        logger.debug(f"Serial data received: {len(chunk)} bytes, buffer now: {len(buffer)}")
                        while '\r\n' in buffer:
                            line, buffer = buffer.split('\r\n', 1)
                            print(f"[RYLR999] Complete line: {line[:80]}...", flush=True)
                            logger.info(f"Complete line received: {line[:100]}")
                            lines_to_process.append(line)
                finally:
                    self._lock.release()

            # Process lines AFTER releasing lock (allows callbacks to use radio.send)
            for line in lines_to_process:
                self._parse_received(line)
            time.sleep(0.05)
        logger.info("RYLR999 listener thread stopped")

    def _parse_received(self, line):
        print(f"[RYLR999] _parse_received called: {line[:80]}...", flush=True)
        if line.startswith('+RCV=') and self.on_receive:
            try:
                # Format: +RCV=<sender>,<length>,<data>,<rssi>,<snr>
                # Data may contain commas (though base64 shouldn't), so parse carefully
                # RSSI and SNR are always last two comma-separated values
                content = line[5:]  # Remove '+RCV='
                parts = content.split(',')
                print(f"[RYLR999] Split into {len(parts)} parts", flush=True)

                sender = int(parts[0])
                length = int(parts[1])
                # RSSI and SNR are the last two parts
                snr = int(parts[-1])
                rssi = int(parts[-2])
                # Data is everything between length and rssi (parts[2:-2] joined)
                data = ','.join(parts[2:-2])

                print(f"[RYLR999] Parsed: sender={sender}, len={length}, data_len={len(data)}, rssi={rssi}, snr={snr}", flush=True)
                print(f"[RYLR999] Data: {data[:60]}...", flush=True)
                print(f"[RYLR999] Calling on_receive callback...", flush=True)

                self.on_receive(sender, data, rssi, snr)
                print(f"[RYLR999] on_receive returned", flush=True)
            except (ValueError, IndexError) as e:
                logger.error(f"Parse error on line '{line[:80]}': {e}")
                print(f"Parse error: {e}")

    def close(self):
        self.stop_listening()
        self.ser.close()


if __name__ == '__main__':
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

    print(f"Connecting to {port}...")
    radio = RYLR999(port)

    print("\n=== Current Configuration ===")
    config = radio.get_config()
    for key, value in config.items():
        print(f"  {key}: {value}")

    print(f"\n  Temperature: {radio.get_temperature()}C")
    print(f"  Firmware: {radio.get_version()}")

    radio.close()
    print("\nDone.")
