# Heltec V3.1 Boot File
# This runs on power-up before main.py

import gc

# Free up memory
gc.collect()

print("=" * 40)
print("Heron Squawk Mesh Node")
print("Heltec LoRa32 V3.1")
print("=" * 40)
print()
print("Quick start:")
print("  from quick_test import *")
print("  setup('your_passphrase')")
print("  join('channel_name')")
print("  msg('channel_name', 'Hello!')")
print("  rx()")
print()
