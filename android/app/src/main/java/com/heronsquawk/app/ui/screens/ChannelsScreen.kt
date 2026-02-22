package com.heronsquawk.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
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
import com.heronsquawk.app.ui.components.ChannelChip
import com.heronsquawk.app.ui.components.MessageBubble
import com.heronsquawk.app.ui.components.MessageInput
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

class ChannelsViewModel(
    private val bleService: BleService,
    private val repository: Repository
) : ViewModel() {
    val connectionState: StateFlow<ConnectionState> = bleService.connectionState

    private val _channels = mutableStateListOf<String>()
    val channels: List<String> get() = _channels

    private val _selectedChannel = MutableStateFlow<String?>(null)
    val selectedChannel: StateFlow<String?> = _selectedChannel.asStateFlow()

    private val _messages = MutableStateFlow<List<Message>>(emptyList())
    val messages: StateFlow<List<Message>> = _messages.asStateFlow()

    val darkTheme: StateFlow<Boolean> = repository.settings.darkTheme
    val callSign: StateFlow<String> = repository.settings.callSign

    init {
        // Listen for BLE responses
        bleService.responses
            .onEach { response ->
                when (response) {
                    is BleResponse.Joined -> {
                        if (!_channels.contains(response.channel)) {
                            _channels.add(response.channel)
                        }
                        if (_selectedChannel.value == null) {
                            selectChannel(response.channel)
                        }
                    }
                    is BleResponse.Left -> {
                        _channels.remove(response.channel)
                        if (_selectedChannel.value == response.channel) {
                            _selectedChannel.value = _channels.firstOrNull()
                        }
                    }
                    is BleResponse.ChannelMessage -> {
                        repository.saveIncomingChannelMessage(
                            channel = response.channel,
                            content = response.content,
                            senderAddress = response.senderAddress,
                            rssi = response.rssi,
                            snr = response.snr
                        )
                    }
                    else -> {}
                }
            }
            .launchIn(viewModelScope)
    }

    fun selectChannel(channel: String) {
        _selectedChannel.value = channel
        repository.getChannelMessages(channel)
            .onEach { _messages.value = it }
            .launchIn(viewModelScope)
    }

    fun joinChannel(channelName: String) {
        if (connectionState.value !is ConnectionState.Connected) return
        if (channelName.isBlank()) return

        viewModelScope.launch {
            bleService.sendJoin(channelName)
        }
    }

    fun leaveChannel(channelName: String) {
        if (connectionState.value !is ConnectionState.Connected) return

        viewModelScope.launch {
            bleService.sendLeave(channelName)
        }
    }

    fun sendMessage(content: String) {
        val channel = _selectedChannel.value ?: return
        if (connectionState.value !is ConnectionState.Connected) return

        viewModelScope.launch {
            val cs = callSign.value
            val messageToSend = if (cs.isNotEmpty()) "$cs: $content" else content
            repository.saveOutgoingChannelMessage(channel, messageToSend)
            bleService.sendMessage(channel, messageToSend)
        }
    }

    fun clearCurrentChannelMessages() {
        val channel = _selectedChannel.value ?: return
        viewModelScope.launch {
            repository.clearChannelMessages(channel)
        }
    }

    companion object {
        fun factory(bleService: BleService, repository: Repository) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return ChannelsViewModel(bleService, repository) as T
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChannelsScreen(
    bleService: BleService,
    repository: Repository,
    modifier: Modifier = Modifier
) {
    val viewModel: ChannelsViewModel = viewModel(factory = ChannelsViewModel.factory(bleService, repository))

    val connectionState by viewModel.connectionState.collectAsState()
    val selectedChannel by viewModel.selectedChannel.collectAsState()
    val messages by viewModel.messages.collectAsState()
    val darkTheme by viewModel.darkTheme.collectAsState()

    var newChannelInput by remember { mutableStateOf("") }
    var messageInput by remember { mutableStateOf("") }

    val listState = rememberLazyListState()
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
            text = "Channels",
            style = MaterialTheme.typography.titleLarge,
            color = if (darkTheme) Color.White else MaterialTheme.colorScheme.onSurface
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Join channel input
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = newChannelInput,
                onValueChange = { newChannelInput = it },
                label = { Text("Join Channel") },
                placeholder = { Text("Channel name") },
                singleLine = true,
                enabled = isConnected,
                modifier = Modifier.weight(1f)
            )

            IconButton(
                onClick = {
                    viewModel.joinChannel(newChannelInput)
                    newChannelInput = ""
                },
                enabled = isConnected && newChannelInput.isNotBlank()
            ) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "Join",
                    tint = if (isConnected && newChannelInput.isNotBlank()) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        if (darkTheme) Color(0xFFD1D5DB) else MaterialTheme.colorScheme.onSurfaceVariant
                    }
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Active channels
        if (viewModel.channels.isNotEmpty()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Active Channels",
                    style = MaterialTheme.typography.titleSmall,
                    color = if (darkTheme) Color.White else MaterialTheme.colorScheme.onSurfaceVariant
                )

                if (selectedChannel != null) {
                    IconButton(
                        onClick = { viewModel.clearCurrentChannelMessages() }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Delete,
                            contentDescription = "Clear chat",
                            tint = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(vertical = 8.dp)
            ) {
                viewModel.channels.forEach { channel ->
                    ChannelChip(
                        channelName = channel,
                        isSelected = channel == selectedChannel,
                        onClick = { viewModel.selectChannel(channel) },
                        onLeave = { viewModel.leaveChannel(channel) }
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Messages
        if (selectedChannel != null) {
            if (messages.isEmpty()) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "No messages in $selectedChannel",
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (darkTheme) Color(0xFFD1D5DB) else MaterialTheme.colorScheme.onSurfaceVariant
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
                placeholder = if (isConnected) "Message $selectedChannel..." else "Connect to send messages"
            )
        } else if (viewModel.channels.isEmpty()) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                    contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (isConnected) "Join a channel to start messaging" else "Connect to a device first",
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (darkTheme) Color(0xFFD1D5DB) else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "Select a channel",
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (darkTheme) Color(0xFFD1D5DB) else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
