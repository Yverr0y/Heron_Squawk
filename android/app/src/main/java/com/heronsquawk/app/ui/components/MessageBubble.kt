package com.heronsquawk.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.heronsquawk.app.data.Message
import com.heronsquawk.app.data.MessageDirection
import com.heronsquawk.app.data.toHexAddress
import com.heronsquawk.app.ui.theme.AppColors
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun MessageBubble(
    message: Message,
    darkTheme: Boolean,
    modifier: Modifier = Modifier
) {
    val isOutgoing = message.direction == MessageDirection.OUTGOING

    val bubbleColor = if (isOutgoing) {
        AppColors.outgoingBubble(darkTheme)
    } else {
        AppColors.incomingBubble(darkTheme)
    }

    val borderColor = if (isOutgoing) {
        AppColors.outgoingBorder(darkTheme)
    } else {
        AppColors.incomingBorder(darkTheme)
    }

    val alignment = if (isOutgoing) Alignment.CenterEnd else Alignment.CenterStart

    Box(
        modifier = modifier.fillMaxWidth(),
        contentAlignment = alignment
    ) {
        Column(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(bubbleColor)
                .border(1.dp, borderColor, RoundedCornerShape(12.dp))
                .padding(12.dp)
        ) {
            // Header with sender/time info
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (!isOutgoing && message.remoteAddress != null) {
                    Text(
                        text = message.remoteAddress.toHexAddress(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                } else if (isOutgoing) {
                    Text(
                        text = "You",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }

                Text(
                    text = formatTime(message.timestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = AppColors.textDim(darkTheme)
                )
            }

            // Message content
            Text(
                text = message.content,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(top = 4.dp)
            )

            // Signal info for incoming messages
            if (!isOutgoing && (message.rssi != null || message.snr != null)) {
                Row(
                    modifier = Modifier.padding(top = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    message.rssi?.let {
                        Text(
                            text = "${it}dB",
                            style = MaterialTheme.typography.labelSmall,
                            color = AppColors.textDim(darkTheme)
                        )
                    }
                    message.snr?.let {
                        Text(
                            text = "SNR: ${"%.1f".format(it)}",
                            style = MaterialTheme.typography.labelSmall,
                            color = AppColors.textDim(darkTheme)
                        )
                    }
                }
            }
        }
    }
}

private fun formatTime(timestamp: Long): String {
    val formatter = SimpleDateFormat("HH:mm", Locale.getDefault())
    return formatter.format(Date(timestamp))
}
