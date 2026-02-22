package com.heronsquawk.app.util

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Format timestamp as HH:mm
 */
fun Long.formatTime(): String {
    val formatter = SimpleDateFormat("HH:mm", Locale.getDefault())
    return formatter.format(Date(this))
}

/**
 * Format timestamp as full date/time
 */
fun Long.formatDateTime(): String {
    val formatter = SimpleDateFormat("MMM dd, HH:mm", Locale.getDefault())
    return formatter.format(Date(this))
}

/**
 * Parse hex string to Int, returning null if invalid
 */
fun String.parseHexAddress(): Int? {
    return try {
        this.toInt(16)
    } catch (e: NumberFormatException) {
        null
    }
}

// Note: toHexAddress() is defined in com.heronsquawk.app.data.Message

/**
 * Truncate string to max length with ellipsis
 */
fun String.truncate(maxLength: Int): String {
    return if (this.length > maxLength) {
        this.take(maxLength - 3) + "..."
    } else {
        this
    }
}
