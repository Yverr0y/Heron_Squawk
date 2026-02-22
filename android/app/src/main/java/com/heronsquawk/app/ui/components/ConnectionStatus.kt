package com.heronsquawk.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.heronsquawk.app.ble.ConnectionState
import com.heronsquawk.app.ui.theme.AccentDanger
import com.heronsquawk.app.ui.theme.AccentSuccess
import com.heronsquawk.app.ui.theme.AccentWarning

@Composable
fun ConnectionStatusIndicator(
    connectionState: ConnectionState,
    modifier: Modifier = Modifier
) {
    val (color, text) = when (connectionState) {
        is ConnectionState.Connected -> AccentSuccess to "Connected"
        is ConnectionState.Connecting -> AccentWarning to "Connecting..."
        is ConnectionState.Scanning -> AccentWarning to "Scanning..."
        is ConnectionState.Disconnected -> AccentDanger to "Disconnected"
        is ConnectionState.Error -> AccentDanger to "Error"
    }

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Box(
            modifier = Modifier
                .size(10.dp)
                .clip(CircleShape)
                .background(color)
        )
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            color = color
        )
    }
}
