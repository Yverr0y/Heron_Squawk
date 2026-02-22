package com.heronsquawk.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.heronsquawk.app.ble.BleResponse
import com.heronsquawk.app.ble.BleService
import com.heronsquawk.app.ble.ConnectionState
import com.heronsquawk.app.data.Message
import com.heronsquawk.app.data.Repository
import com.heronsquawk.app.ui.components.MessageBubble
import com.heronsquawk.app.ui.components.MessageInput
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

class DmViewModel(
    private val bleService: BleService,
    private val repository: Repository
) : ViewModel() {
    val connectionState: StateFlow<ConnectionState> = bleService.connectionState

    private val _targetAddress = MutableStateFlow<Int?>(null)
    val targetAddress: StateFlow<Int?> = _targetAddress.asStateFlow()

    private val _messages = MutableStateFlow<List<Message>>(emptyList())
    val messages: StateFlow<List<Message>> = _messages.asStateFlow()

    private val _dmAddresses = MutableStateFlow<List<Int>>(emptyList())
    val dmAddresses: StateFlow<List<Int>> = _dmAddresses.asStateFlow()

    val darkTheme: StateFlow<Boolean> = repository.settings.darkTheme
    val callSign: StateFlow<String> = repository.settings.callSign

    init {
        // Collect DM addresses
        repository.getDmAddresses()
            .onEach { _dmAddresses.value = it }
            .launchIn(viewModelScope)

        // Listen for incoming DMs
        bleService.responses
            .onEach { response ->
                if (response is BleResponse.DirectMessage) {
                    repository.saveIncomingDm(
                        senderAddress = response.senderAddress,
                        content = response.content,
                        rssi = response.rssi,
                        snr = response.snr
                    )
                }
            }
            .launchIn(viewModelScope)
    }

    fun setTargetAddress(addressStr: String) {
        val address = addressStr.toIntOrNull()
        if (address != null && address in 1..65535) {
            _targetAddress.value = address
            repository.getDirectMessages(address)
                .onEach { _messages.value = it }
                .launchIn(viewModelScope)
        } else {
            _targetAddress.value = null
            _messages.value = emptyList()
        }
    }

    fun sendMessage(content: String) {
        val address = _targetAddress.value ?: return
        if (connectionState.value !is ConnectionState.Connected) return

        viewModelScope.launch {
            val cs = callSign.value
            val messageToSend = if (cs.isNotEmpty()) "$cs: $content" else content
            repository.saveOutgoingDm(address, messageToSend)
            bleService.sendDm(address, messageToSend)
        }
    }

    fun clearMessages() {
        val address = _targetAddress.value ?: return
        viewModelScope.launch {
            repository.clearDirectMessages(address)
        }
    }

    companion object {
        fun factory(bleService: BleService, repository: Repository) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return DmViewModel(bleService, repository) as T
            }
        }
    }
}

@Composable
fun DmScreen(
    bleService: BleService,
    repository: Repository,
    modifier: Modifier = Modifier
) {
    val viewModel: DmViewModel = viewModel(factory = DmViewModel.factory(bleService, repository))

    val connectionState by viewModel.connectionState.collectAsState()
    val targetAddress by viewModel.targetAddress.collectAsState()
    val messages by viewModel.messages.collectAsState()
    val dmAddresses by viewModel.dmAddresses.collectAsState()
    val darkTheme by viewModel.darkTheme.collectAsState()

    var addressInput by remember { mutableStateOf("") }
    var messageInput by remember { mutableStateOf("") }

    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    val isConnected = connectionState is ConnectionState.Connected

    // Scroll to bottom when new messages arrive
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Direct Messages",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onSurface
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Address input
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = addressInput,
                onValueChange = { input ->
                    // Only allow digits
                    val filtered = input.filter { it.isDigit() }
                    addressInput = filtered
                    viewModel.setTargetAddress(filtered)
                },
                label = { Text("Address") },
                placeholder = { Text("1-65535") },
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Number
                ),
                singleLine = true,
                modifier = Modifier.weight(1f)
            )

            if (targetAddress != null) {
                IconButton(
                    onClick = { viewModel.clearMessages() }
                ) {
                    Icon(
                        imageVector = Icons.Default.Delete,
                        contentDescription = "Clear chat",
                        tint = MaterialTheme.colorScheme.error
                    )
                }
            }
        }

        // Recent addresses
        if (dmAddresses.isNotEmpty() && targetAddress == null) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Recent:",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(top = 4.dp)
            ) {
                dmAddresses.take(5).forEach { addr ->
                    TextButton(
                        onClick = {
                            addressInput = addr.toString()
                            viewModel.setTargetAddress(addr.toString())
                        }
                    ) {
                        Text(addr.toString())
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Messages list
        if (targetAddress != null) {
            if (messages.isEmpty()) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "No messages with $targetAddress",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    state = listState,
                    contentPadding = PaddingValues(vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(messages) { message ->
                        MessageBubble(
                            message = message,
                            darkTheme = darkTheme
                        )
                    }
                }
            }

            // Message input
            Spacer(modifier = Modifier.height(8.dp))
            MessageInput(
                value = messageInput,
                onValueChange = { messageInput = it },
                onSend = {
                    viewModel.sendMessage(messageInput)
                    messageInput = ""
                },
                enabled = isConnected,
                placeholder = if (isConnected) "Type a message..." else "Connect to send messages"
            )
        } else {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "Enter a device address to start messaging",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
