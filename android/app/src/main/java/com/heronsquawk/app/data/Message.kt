package com.heronsquawk.app.data

import androidx.room.Entity
import androidx.room.PrimaryKey

enum class MessageType {
    CHANNEL,
    DM
}

enum class MessageDirection {
    INCOMING,
    OUTGOING
}

@Entity(tableName = "messages")
data class Message(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    val type: MessageType,
    val direction: MessageDirection,

    // For channel messages
    val channel: String? = null,

    // For DMs - remote address as hex int (e.g., 0x1A2B = 6699)
    val remoteAddress: Int? = null,

    val content: String,
    val timestamp: Long = System.currentTimeMillis(),

    // Signal info (incoming messages only)
    val rssi: Int? = null,
    val snr: Float? = null
) {
    companion object {
        fun channelMessage(
            channel: String,
            content: String,
            direction: MessageDirection,
            remoteAddress: Int? = null,
            rssi: Int? = null,
            snr: Float? = null
        ) = Message(
            type = MessageType.CHANNEL,
            direction = direction,
            channel = channel,
            content = content,
            remoteAddress = remoteAddress,
            rssi = rssi,
            snr = snr
        )

        fun directMessage(
            remoteAddress: Int,
            content: String,
            direction: MessageDirection,
            rssi: Int? = null,
            snr: Float? = null
        ) = Message(
            type = MessageType.DM,
            direction = direction,
            remoteAddress = remoteAddress,
            content = content,
            rssi = rssi,
            snr = snr
        )
    }
}

// Extension to format address as hex string
fun Int.toHexAddress(): String = String.format("%04X", this)
