package com.heronsquawk.app.ui.screens

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.heronsquawk.app.ble.BleService
import com.heronsquawk.app.ble.ConnectionState
import com.heronsquawk.app.ble.ScannedDevice
import com.heronsquawk.app.ui.components.ConnectedDeviceCard
import com.heronsquawk.app.ui.components.ConnectionStatusIndicator
import com.heronsquawk.app.ui.components.DeviceCard
import kotlinx.coroutines.flow.StateFlow

class DeviceViewModel(private val bleService: BleService) : ViewModel() {
    val connectionState: StateFlow<ConnectionState> = bleService.connectionState
    val scannedDevices: StateFlow<List<ScannedDevice>> = bleService.scannedDevices

    val isBluetoothEnabled: Boolean
        get() = bleService.isBluetoothEnabled

    fun startScan() {
        bleService.startScan()
    }

    fun stopScan() {
        bleService.stopScan()
    }

    fun connect(scannedDevice: ScannedDevice) {
        bleService.connect(scannedDevice.device)
    }

    fun disconnect() {
        bleService.disconnect()
    }

    companion object {
        fun factory(bleService: BleService) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return DeviceViewModel(bleService) as T
            }
        }
    }
}

@Composable
fun DeviceScreen(
    bleService: BleService,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val viewModel: DeviceViewModel = viewModel(factory = DeviceViewModel.factory(bleService))

    val connectionState by viewModel.connectionState.collectAsState()
    val scannedDevices by viewModel.scannedDevices.collectAsState()

    var hasPermissions by remember { mutableStateOf(false) }

    // Permission launcher
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        hasPermissions = permissions.values.all { it }
        if (hasPermissions) {
            viewModel.startScan()
        }
    }

    // Request permissions on first composition
    LaunchedEffect(Unit) {
        val permissions = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT
            )
        } else {
            arrayOf(
                Manifest.permission.BLUETOOTH,
                Manifest.permission.BLUETOOTH_ADMIN,
                Manifest.permission.ACCESS_FINE_LOCATION
            )
        }
        permissionLauncher.launch(permissions)
    }

    // Stop scan when leaving screen
    DisposableEffect(Unit) {
        onDispose {
            if (connectionState is ConnectionState.Scanning) {
                viewModel.stopScan()
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // Connection status
        ConnectionStatusIndicator(
            connectionState = connectionState,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        // Connected device section
        when (val state = connectionState) {
            is ConnectionState.Connected -> {
                Text(
                    text = "Connected Device",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
                ConnectedDeviceCard(
                    deviceName = state.deviceName,
                    deviceAddress = state.deviceAddress,
                    onDisconnect = { viewModel.disconnect() }
                )
                Spacer(modifier = Modifier.height(24.dp))
            }
            else -> {}
        }

        // Available devices section
        Box(
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = "Available Devices",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface
            )

            IconButton(
                onClick = {
                    if (connectionState is ConnectionState.Scanning) {
                        viewModel.stopScan()
                    } else {
                        viewModel.startScan()
                    }
                },
                modifier = Modifier.align(Alignment.CenterEnd)
            ) {
                if (connectionState is ConnectionState.Scanning) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        strokeWidth = 2.dp
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Scan",
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        if (!viewModel.isBluetoothEnabled) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "Please enable Bluetooth",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.error
                )
            }
        } else if (scannedDevices.isEmpty() && connectionState !is ConnectionState.Scanning) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = "No devices found",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(onClick = { viewModel.startScan() }) {
                        Text("Scan for devices")
                    }
                }
            }
        } else {
            LazyColumn(
                contentPadding = PaddingValues(vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(scannedDevices) { device ->
                    DeviceCard(
                        device = device,
                        onConnect = { viewModel.connect(device) }
                    )
                }
            }
        }
    }
}
