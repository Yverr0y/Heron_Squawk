#!/usr/bin/env python3
"""
Simple RYLR999 radio test - run on TWO separate terminals
Usage:
  Terminal 1 (receiver): python radio_test.py /dev/ttyUSB0 listen
  Terminal 2 (sender):   python radio_test.py /dev/ttyUSB1 send
"""

import sys
import time
from rylr999 import RYLR999

def on_receive(sender, data, rssi, snr):
    print(f"\n*** RECEIVED ***")
    print(f"From: {sender}")
    print(f"Data: {data}")
    print(f"RSSI: {rssi}, SNR: {snr}")
    print("****************\n")

def main():
    if len(sys.argv) < 3:
        print("Usage: python radio_test.py <COM_PORT> <listen|send>")
        print("Example:")
        print("  Terminal 1: python radio_test.py /dev/ttyUSB0 listen")
        print("  Terminal 2: python radio_test.py /dev/ttyUSB1 send")
        sys.exit(1)

    port = sys.argv[1]
    mode = sys.argv[2]

    print(f"Connecting to {port}...")
    radio = RYLR999(port)

    config = radio.get_config()
    print(f"Address: {config['address']}")
    print(f"Network ID: {config['network_id']}")
    print(f"Frequency: {config['frequency']} Hz")

    if mode == "listen":
        print("\n=== LISTENING MODE ===")
        print("Waiting for messages... (Ctrl+C to stop)")
        radio.start_listening(on_receive)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
        radio.close()

    elif mode == "send":
        dest = input("Enter destination address: ").strip()
        dest = int(dest)

        print(f"\n=== SEND MODE ===")
        print(f"Sending to address {dest}")
        print("Type messages and press Enter. Type 'quit' to exit.\n")

        try:
            while True:
                msg = input("> ")
                if msg.lower() == 'quit':
                    break
                result = radio.send(dest, msg)
                print(f"Send result: {'OK' if result else 'FAILED'}")
        except KeyboardInterrupt:
            pass

        radio.close()
        print("Done.")
    else:
        print(f"Unknown mode: {mode}")
        print("Use 'listen' or 'send'")

if __name__ == "__main__":
    main()
