package com.heronsquawk.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.heronsquawk.app.ble.BleResponse
import com.heronsquawk.app.ble.BleService
import com.heronsquawk.app.ble.ConnectionState
import com.heronsquawk.app.ble.DeviceConfig
import com.heronsquawk.app.ble.ResponseParser
import com.heronsquawk.app.data.Repository
import com.heronsquawk.app.data.toHexAddress
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

class SettingsViewModel(
    private val bleService: BleService,
    private val repository: Repository
) : ViewModel() {
    val connectionState: StateFlow<ConnectionState> = bleService.connectionState
    val darkTheme: StateFlow<Boolean> = repository.settings.darkTheme
    val autoReconnect: StateFlow<Boolean> = repository.settings.autoReconnect
    val callSign: StateFlow<String> = repository.settings.callSign

    private val _deviceConfig = MutableStateFlow<DeviceConfig?>(null)
    val deviceConfig: StateFlow<DeviceConfig?> = _deviceConfig.asStateFlow()

    private val _initStatus = MutableStateFlow<String?>(null)
    val initStatus: StateFlow<String?> = _initStatus.asStateFlow()

    init {
        bleService.responses
            .onEach { response ->
                when (response) {
                    is BleResponse.Config -> {
                        _deviceConfig.value = ResponseParser.parseDeviceConfig(response.json)
                    }
                    is BleResponse.KeyStatus -> {
                        _initStatus.value = when (response.status) {
                            "DERIVING" -> "Deriving key..."
                            "READY" -> {
                                // Auto-start listening when key is ready
                                viewModelScope.launch {
                                    bleService.sendListenStart()
                                }
                                "Key ready - listening!"
                            }
                            else -> response.status
                        }
                    }
                    is BleResponse.Ok -> {
                        _initStatus.value = "Settings Saved Successfully"
                    }
                    is BleResponse.Error -> {
                        _initStatus.value = "Error: ${response.message}"
                    }
                    else -> {}
                }
            }
            .launchIn(viewModelScope)
    }

    fun setDarkTheme(enabled: Boolean) = repository.settings.setDarkTheme(enabled)
    fun setAutoReconnect(enabled: Boolean) = repository.settings.setAutoReconnect(enabled)
    fun setCallSign(callSign: String) = repository.settings.setCallSign(callSign)

    fun refreshConfig() {
        if (connectionState.value is ConnectionState.Connected) {
            viewModelScope.launch { bleService.sendConfigGet() }
        }
    }

    fun savePassphrase(passphrase: String) {
        if (connectionState.value !is ConnectionState.Connected) return
        viewModelScope.launch {
            _initStatus.value = "Saving passphrase..."
            // These are now suspend calls that wait for GATT write confirmation
            bleService.sendConfigSet("passphrase", passphrase)
            delay(200) // Extra safety gap
            bleService.sendConfigSave()
            repository.settings.setPassphrase(passphrase)
        }
    }

    fun saveAddress(address: Int) {
        if (connectionState.value !is ConnectionState.Connected) return
        if (address < 1 || address > 65535) {
            _initStatus.value = "Error: Address must be 1-65535"
            return
        }
        viewModelScope.launch {
            _initStatus.value = "Saving address..."
            bleService.sendConfigSet("address", address.toString())
            delay(200)
            bleService.sendConfigSave()
            delay(200)
            refreshConfig()
        }
    }

    fun initialize() {
        if (connectionState.value !is ConnectionState.Connected) return
        viewModelScope.launch {
            _initStatus.value = "Initializing..."
            bleService.sendInit()
        }
    }

    fun disconnect() = bleService.disconnect()
    fun clearAllMessages() = viewModelScope.launch { repository.clearAllMessages() }

    companion object {
        fun factory(bleService: BleService, repository: Repository) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return SettingsViewModel(bleService, repository) as T
            }
        }
    }
}

@Composable
fun SettingsScreen(
    bleService: BleService,
    repository: Repository,
    modifier: Modifier = Modifier
) {
    val viewModel: SettingsViewModel = viewModel(factory = SettingsViewModel.factory(bleService, repository))
    val connectionState by viewModel.connectionState.collectAsState()
    val darkTheme by viewModel.darkTheme.collectAsState()
    val autoReconnect by viewModel.autoReconnect.collectAsState()
    val callSign by viewModel.callSign.collectAsState()
    val deviceConfig by viewModel.deviceConfig.collectAsState()
    val initStatus by viewModel.initStatus.collectAsState()

    var passphraseInput by remember { mutableStateOf("") }
    var showPassphrase by remember { mutableStateOf(false) }
    var addressInput by remember { mutableStateOf("") }
    var callSignInput by remember { mutableStateOf(callSign) }
    val isConnected = connectionState is ConnectionState.Connected

    // Update callSignInput when setting loads
    LaunchedEffect(callSign) {
        callSignInput = callSign
    }

    // Update address input when config loads
    LaunchedEffect(deviceConfig) {
        deviceConfig?.let {
            if (addressInput.isEmpty() && it.address > 0) {
                addressInput = it.address.toString()
            }
        }
    }

    LaunchedEffect(connectionState) {
        if (connectionState is ConnectionState.Connected) {
            viewModel.refreshConfig()
        }
    }

    Column(
        modifier = modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)
    ) {
        Text(
            text = "Settings",
            style = MaterialTheme.typography.titleLarge,
            color = if (darkTheme) Color.White else Color.Unspecified
        )
        Spacer(modifier = Modifier.height(24.dp))

        SectionCard(title = "Device Configuration", darkTheme = darkTheme) {
            OutlinedTextField(
                value = addressInput,
                onValueChange = { newValue ->
                    // Only allow digits
                    if (newValue.isEmpty() || newValue.all { it.isDigit() }) {
                        addressInput = newValue
                    }
                },
                label = { Text("Device Address") },
                placeholder = { Text("1-65535") },
                enabled = isConnected,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = {
                    addressInput.toIntOrNull()?.let { viewModel.saveAddress(it) }
                },
                enabled = isConnected && addressInput.isNotBlank() && (addressInput.toIntOrNull() ?: 0) in 1..65535,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Save Address")
            }
            Spacer(modifier = Modifier.height(16.dp))
            OutlinedTextField(
                value = passphraseInput,
                onValueChange = { passphraseInput = it },
                label = { Text("Passphrase") },
                placeholder = { Text("Enter mesh passphrase") },
                visualTransformation = if (showPassphrase) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { showPassphrase = !showPassphrase }) {
                        Icon(
                            imageVector = if (showPassphrase) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                            contentDescription = null
                        )
                    }
                },
                enabled = isConnected,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = { viewModel.savePassphrase(passphraseInput) },
                enabled = isConnected && passphraseInput.isNotBlank(),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Save Passphrase")
            }
            Spacer(modifier = Modifier.height(16.dp))
            deviceConfig?.let { config ->
                InfoRow(label = "Current Address", value = config.address.toString(), darkTheme = darkTheme)
                InfoRow(label = "Node Name", value = config.node_name.ifEmpty { "(not set)" }, darkTheme = darkTheme)
                InfoRow(label = "Passphrase Set", value = if (config.passphrase_set) "Yes" else "No", darkTheme = darkTheme)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))
        SectionCard(title = "Radio Configuration", darkTheme = darkTheme) {
            deviceConfig?.let { config ->
                val freqMhz = config.frequency / 1_000_000.0
                val bwMap = mapOf(7 to "125 kHz", 8 to "250 kHz", 9 to "500 kHz")
                InfoRow(label = "Frequency", value = "%.3f MHz".format(freqMhz), darkTheme = darkTheme)
                InfoRow(label = "TX Power", value = "${config.tx_power} dBm", darkTheme = darkTheme)
                InfoRow(label = "Spreading Factor", value = "SF${config.spreading_factor}", darkTheme = darkTheme)
                InfoRow(label = "Bandwidth", value = bwMap[config.bandwidth] ?: "${config.bandwidth}", darkTheme = darkTheme)
                InfoRow(label = "Coding Rate", value = "4/${config.coding_rate + 4}", darkTheme = darkTheme)
                InfoRow(label = "Preamble", value = "${config.preamble} symbols", darkTheme = darkTheme)
                InfoRow(label = "Network ID", value = "${config.network_id}", darkTheme = darkTheme)
            } ?: run {
                Text(
                    text = if (isConnected) "Loading..." else "Connect to device to view",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (darkTheme) Color(0xFFD1D5DB) else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))
        SectionCard(title = "App Settings", darkTheme = darkTheme) {
            OutlinedTextField(
                value = callSignInput,
                onValueChange = { callSignInput = it },
                label = { Text("Call Sign / Name") },
                placeholder = { Text("e.g. Bob, K1ABC") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = { viewModel.setCallSign(callSignInput) },
                enabled = callSignInput != callSign,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Save Call Sign")
            }
            if (callSign.isNotEmpty()) {
                Text(
                    text = "Messages will be sent as: $callSign: <message>",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (darkTheme) Color(0xFFD1D5DB) else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            SettingRow(label = "Dark Theme", checked = darkTheme, onCheckedChange = { viewModel.setDarkTheme(it) }, darkTheme = darkTheme)
            SettingRow(label = "Auto-reconnect", checked = autoReconnect, onCheckedChange = { viewModel.setAutoReconnect(it) }, darkTheme = darkTheme)
        }

        Spacer(modifier = Modifier.height(16.dp))
        SectionCard(title = "Actions", darkTheme = darkTheme) {
            OutlinedButton(
                onClick = { viewModel.clearAllMessages() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)
            ) {
                Text("Clear All Messages")
            }
            Spacer(modifier = Modifier.height(8.dp))
            if (isConnected) {
                OutlinedButton(
                    onClick = { viewModel.disconnect() },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Disconnect Device")
                }
            }
        }

        Spacer(modifier = Modifier.weight(1f))
        Column(modifier = Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            initStatus?.let { status ->
                Text(
                    text = status,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (status.contains("Error")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
            }
            Button(
                onClick = { viewModel.initialize() },
                enabled = isConnected,
                modifier = Modifier.fillMaxWidth().height(56.dp)
            ) {
                Text(text = "INITIALIZE DEVICE", style = MaterialTheme.typography.titleMedium)
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
    }
}

@Composable
private fun SectionCard(title: String, darkTheme: Boolean, content: @Composable () -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.surfaceVariant).border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(12.dp)).padding(16.dp)
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(bottom = 12.dp)
        )
        content()
    }
}

@Composable
private fun SettingRow(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit, darkTheme: Boolean) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = if (darkTheme) Color.White else Color.Unspecified
        )
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun InfoRow(label: String, value: String, darkTheme: Boolean) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = if (darkTheme) Color(0xFFD1D5DB) else MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = if (darkTheme) Color.White else Color.Unspecified
        )
    }
}
