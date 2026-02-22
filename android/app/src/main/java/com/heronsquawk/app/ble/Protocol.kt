package com.heronsquawk.app.ble

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * BLE Protocol for communicating with Heltec device.
 *
 * Commands (App → Device):
 * - PING
 * - CONFIG:GET
 * - CONFIG:SET:key:value
 * - CONFIG:SAVE
 * - JOIN:channel_name
 * - LEAVE:channel_name
 * - SEND:channel_name:message
 * - DM:address:message
 * - LISTEN:START
 * - LISTEN:STOP
 * - INIT
 * - STATUS
 *
 * Responses (Device → App):
 * - PONG
 * - OK
 * - ERR:code:message
 * - CONFIG:{json}
 * - MSG:channel:src_addr:rssi:snr:content
 * - DM:src_addr:rssi:snr:content
 * - STATUS:{json}
 * - JOINED:channel_name
 * - LEFT:channel_name
 * - SENT:channel_name
 * - KEY:DERIVING / KEY:READY
 */

object Protocol {
    // Commands
    fun ping() = "PING"
    fun configGet() = "CONFIG:GET"
    fun configSet(key: String, value: String) = "CONFIG:SET:$key:$value"
    fun configSave() = "CONFIG:SAVE"
    fun join(channel: String) = "JOIN:$channel"
    fun leave(channel: String) = "LEAVE:$channel"
    fun send(channel: String, message: String) = "SEND:$channel:$message"
    fun dm(address: Int, message: String) = "DM:${address.toString(16).uppercase()}:$message"
    fun listenStart() = "LISTEN:START"
    fun listenStop() = "LISTEN:STOP"
    fun init() = "INIT"
    fun status() = "STATUS"
}

sealed class BleResponse {
    data object Pong : BleResponse()
    data object Ok : BleResponse()
    data class Error(val code: String, val message: String) : BleResponse()
    data class Config(val json: String) : BleResponse()
    data class ChannelMessage(
        val channel: String,
        val senderAddress: Int,
        val rssi: Int,
        val snr: Float,
        val content: String
    ) : BleResponse()
    data class DirectMessage(
        val senderAddress: Int,
        val rssi: Int,
        val snr: Float,
        val content: String
    ) : BleResponse()
    data class Status(val json: String) : BleResponse()
    data class Joined(val channel: String) : BleResponse()
    data class Left(val channel: String) : BleResponse()
    data class Sent(val channel: String) : BleResponse()
    data class KeyStatus(val status: String) : BleResponse()
    data class Unknown(val raw: String) : BleResponse()
}

@Serializable
data class DeviceConfig(
    val address: Int = 0,
    val passphrase: String = "",
    val network_id: Int = 18,
    val frequency: Int = 915000000,
    val spreading_factor: Int = 9,
    val bandwidth: Int = 7,
    val coding_rate: Int = 1,
    val preamble: Int = 12,
    val tx_power: Int = 22,
    val passphrase_set: Boolean = false,
    val node_name: String = ""
)

@Serializable
data class DeviceStatus(
    val listening: Boolean = false,
    val channels: List<String> = emptyList(),
    val initialized: Boolean = false
)

object ResponseParser {
    private val json = Json { ignoreUnknownKeys = true }

    fun parse(response: String): BleResponse {
        val trimmed = response.trim()

        return when {
            trimmed == "PONG" -> BleResponse.Pong
            trimmed == "OK" -> BleResponse.Ok
            trimmed.startsWith("ERR:") -> parseError(trimmed)
            trimmed.startsWith("CONFIG:") -> parseConfig(trimmed)
            trimmed.startsWith("MSG:") -> parseChannelMessage(trimmed)
            trimmed.startsWith("DM:") && trimmed.count { it == ':' } >= 4 -> parseDirectMessage(trimmed)
            trimmed.startsWith("STATUS:") -> parseStatus(trimmed)
            trimmed.startsWith("JOINED:") -> BleResponse.Joined(trimmed.substringAfter("JOINED:"))
            trimmed.startsWith("LEFT:") -> BleResponse.Left(trimmed.substringAfter("LEFT:"))
            trimmed.startsWith("SENT:") -> BleResponse.Sent(trimmed.substringAfter("SENT:"))
            trimmed.startsWith("KEY:") -> BleResponse.KeyStatus(trimmed.substringAfter("KEY:"))
            else -> BleResponse.Unknown(trimmed)
        }
    }

    private fun parseError(response: String): BleResponse.Error {
        // ERR:code:message
        val parts = response.split(":", limit = 3)
        return if (parts.size >= 3) {
            BleResponse.Error(parts[1], parts[2])
        } else {
            BleResponse.Error("UNKNOWN", response)
        }
    }

    private fun parseConfig(response: String): BleResponse.Config {
        // CONFIG:{json}
        val jsonStr = response.substringAfter("CONFIG:")
        return BleResponse.Config(jsonStr)
    }

    private fun parseChannelMessage(response: String): BleResponse {
        // MSG:channel:src_addr:rssi:snr:content
        val parts = response.split(":", limit = 6)
        return if (parts.size >= 6) {
            try {
                BleResponse.ChannelMessage(
                    channel = parts[1],
                    senderAddress = parts[2].toInt(16),
                    rssi = parts[3].toIntOrNull() ?: 0,
                    snr = parts[4].toFloatOrNull() ?: 0f,
                    content = parts[5]
                )
            } catch (e: Exception) {
                BleResponse.Unknown(response)
            }
        } else {
            BleResponse.Unknown(response)
        }
    }

    private fun parseDirectMessage(response: String): BleResponse {
        // DM:src_addr:rssi:snr:content
        val parts = response.split(":", limit = 5)
        return if (parts.size >= 5) {
            try {
                BleResponse.DirectMessage(
                    senderAddress = parts[1].toInt(16),
                    rssi = parts[2].toIntOrNull() ?: 0,
                    snr = parts[3].toFloatOrNull() ?: 0f,
                    content = parts[4]
                )
            } catch (e: Exception) {
                BleResponse.Unknown(response)
            }
        } else {
            BleResponse.Unknown(response)
        }
    }

    private fun parseStatus(response: String): BleResponse.Status {
        // STATUS:{json}
        val jsonStr = response.substringAfter("STATUS:")
        return BleResponse.Status(jsonStr)
    }

    fun parseDeviceConfig(jsonStr: String): DeviceConfig? {
        return try {
            json.decodeFromString<DeviceConfig>(jsonStr)
        } catch (e: Exception) {
            null
        }
    }

    fun parseDeviceStatus(jsonStr: String): DeviceStatus? {
        return try {
            json.decodeFromString<DeviceStatus>(jsonStr)
        } catch (e: Exception) {
            null
        }
    }
}
