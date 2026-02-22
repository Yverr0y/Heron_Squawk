package com.heronsquawk.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Build
import android.util.Log
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import java.util.UUID

private const val TAG = "BleService"

// Nordic UART Service UUIDs
private val NUS_SERVICE_UUID = UUID.fromString("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
private val NUS_RX_UUID = UUID.fromString("6E400002-B5A3-F393-E0A9-E50E24DCCA9E") // Write to device
private val NUS_TX_UUID = UUID.fromString("6E400003-B5A3-F393-E0A9-E50E24DCCA9E") // Notify from device
private val CCCD_UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

sealed class ConnectionState {
    data object Disconnected : ConnectionState()
    data object Scanning : ConnectionState()
    data object Connecting : ConnectionState()
    data class Connected(val deviceName: String, val deviceAddress: String) : ConnectionState()
    data class Error(val message: String) : ConnectionState()
}

data class ScannedDevice(
    val device: BluetoothDevice,
    val name: String,
    val address: String,
    val rssi: Int
)

@SuppressLint("MissingPermission")
class BleService private constructor(private val context: Context) {
    private val bluetoothManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager.adapter
    private val bleScanner = bluetoothAdapter?.bluetoothLeScanner

    private var bluetoothGatt: BluetoothGatt? = null
    private var rxCharacteristic: BluetoothGattCharacteristic? = null
    private var txCharacteristic: BluetoothGattCharacteristic? = null

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val sendMutex = Mutex()
    private var writeResult: CompletableDeferred<Int>? = null

    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _scannedDevices = MutableStateFlow<List<ScannedDevice>>(emptyList())
    val scannedDevices: StateFlow<List<ScannedDevice>> = _scannedDevices.asStateFlow()

    private val _responses = MutableSharedFlow<BleResponse>()
    val responses: SharedFlow<BleResponse> = _responses.asSharedFlow()

    private val _rawResponses = MutableSharedFlow<String>()
    val rawResponses: SharedFlow<String> = _rawResponses.asSharedFlow()

    private var responseBuffer = StringBuilder()

    val isBluetoothEnabled: Boolean
        get() = bluetoothAdapter?.isEnabled == true

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val device = result.device
            val name = device.name ?: return
            if (!name.startsWith("HSQ-")) return
            val scannedDevice = ScannedDevice(device, name, device.address, result.rssi)
            val currentList = _scannedDevices.value.toMutableList()
            val existingIndex = currentList.indexOfFirst { it.address == device.address }
            if (existingIndex >= 0) currentList[existingIndex] = scannedDevice else currentList.add(scannedDevice)
            currentList.sortByDescending { it.rssi }
            _scannedDevices.value = currentList
        }
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) gatt.requestMtu(512)
            else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                cleanup()
                _connectionState.value = ConnectionState.Disconnected
            }
        }

        override fun onMtuChanged(gatt: BluetoothGatt, mtu: Int, status: Int) {
            gatt.discoverServices()
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            val nusService = gatt.getService(NUS_SERVICE_UUID)
            rxCharacteristic = nusService?.getCharacteristic(NUS_RX_UUID)
            txCharacteristic = nusService?.getCharacteristic(NUS_TX_UUID)
            if (txCharacteristic != null) {
                gatt.setCharacteristicNotification(txCharacteristic, true)
                val descriptor = txCharacteristic!!.getDescriptor(CCCD_UUID)
                descriptor?.let {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        gatt.writeDescriptor(it, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                    } else {
                        @Suppress("DEPRECATION")
                        it.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                        @Suppress("DEPRECATION")
                        gatt.writeDescriptor(it)
                    }
                }
                _connectionState.value = ConnectionState.Connected(gatt.device.name ?: "Unknown", gatt.device.address)
            }
        }

        override fun onCharacteristicWrite(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            writeResult?.complete(status)
        }

        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            if (characteristic.uuid == NUS_TX_UUID) handleReceivedData(value)
        }
    }

    private fun handleReceivedData(data: ByteArray) {
        responseBuffer.append(String(data, Charsets.UTF_8))
        while (true) {
            val newlineIndex = responseBuffer.indexOf('\n')
            if (newlineIndex < 0) break
            val line = responseBuffer.substring(0, newlineIndex).trim()
            responseBuffer.delete(0, newlineIndex + 1)
            if (line.isNotEmpty()) scope.launch {
                _rawResponses.emit(line)
                _responses.emit(ResponseParser.parse(line))
            }
        }
    }

    suspend fun send(command: String) {
        val gatt = bluetoothGatt ?: return
        val rx = rxCharacteristic ?: return

        sendMutex.withLock {
            val data = (command + "\n").toByteArray(Charsets.UTF_8)
            val chunkSize = 20
            var offset = 0

            while (offset < data.size) {
                val end = minOf(offset + chunkSize, data.size)
                val chunk = data.copyOfRange(offset, end)
                writeResult = CompletableDeferred()

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    gatt.writeCharacteristic(rx, chunk, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
                } else {
                    @Suppress("DEPRECATION")
                    rx.value = chunk
                    @Suppress("DEPRECATION")
                    rx.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                    @Suppress("DEPRECATION")
                    gatt.writeCharacteristic(rx)
                }

                // Wait for onCharacteristicWrite callback with timeout
                withTimeoutOrNull(1000) { writeResult?.await() }
                offset = end
                delay(10) // Small stability delay
            }
            delay(50)
        }
    }

    fun startScan() {
        _scannedDevices.value = emptyList()
        _connectionState.value = ConnectionState.Scanning
        bleScanner?.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), scanCallback)
    }

    fun stopScan() {
        bleScanner?.stopScan(scanCallback)
        if (_connectionState.value is ConnectionState.Scanning) _connectionState.value = ConnectionState.Disconnected
    }

    fun connect(device: BluetoothDevice) {
        stopScan()
        _connectionState.value = ConnectionState.Connecting
        bluetoothGatt = device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
    }

    fun disconnect() = bluetoothGatt?.disconnect()

    private fun cleanup() {
        bluetoothGatt?.close()
        bluetoothGatt = null
        rxCharacteristic = null
        txCharacteristic = null
        responseBuffer.clear()
    }

    // Now Suspendable Wrappers
    suspend fun sendPing() = send(Protocol.ping())
    suspend fun sendInit() = send(Protocol.init())
    suspend fun sendConfigGet() = send(Protocol.configGet())
    suspend fun sendConfigSet(key: String, value: String) = send(Protocol.configSet(key, value))
    suspend fun sendConfigSave() = send(Protocol.configSave())
    suspend fun sendJoin(channel: String) = send(Protocol.join(channel))
    suspend fun sendLeave(channel: String) = send(Protocol.leave(channel))
    suspend fun sendMessage(channel: String, message: String) = send(Protocol.send(channel, message))
    suspend fun sendDm(address: Int, message: String) = send(Protocol.dm(address, message))
    suspend fun sendListenStart() = send(Protocol.listenStart())
    suspend fun sendListenStop() = send(Protocol.listenStop())
    suspend fun sendStatus() = send(Protocol.status())

    companion object {
        @Volatile private var INSTANCE: BleService? = null
        fun getInstance(context: Context) = INSTANCE ?: synchronized(this) { BleService(context.applicationContext).also { INSTANCE = it } }
    }
}
