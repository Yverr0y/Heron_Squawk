package com.heronsquawk.app.data

import android.content.Context
import kotlinx.coroutines.flow.Flow

class Repository private constructor(context: Context) {
    private val database = AppDatabase.getInstance(context)
    private val messageDao = database.messageDao()
    val settings = Settings.getInstance(context)

    // Message operations
    suspend fun saveMessage(message: Message): Long {
        return messageDao.insert(message)
    }

    fun getChannelMessages(channel: String): Flow<List<Message>> {
        return messageDao.getChannelMessages(channel)
    }

    fun getDirectMessages(address: Int): Flow<List<Message>> {
        return messageDao.getDirectMessages(address)
    }

    fun getDmAddresses(): Flow<List<Int>> {
        return messageDao.getDmAddresses()
    }

    suspend fun clearChannelMessages(channel: String) {
        messageDao.clearChannelMessages(channel)
    }

    suspend fun clearDirectMessages(address: Int) {
        messageDao.clearDirectMessages(address)
    }

    suspend fun clearAllMessages() {
        messageDao.clearAll()
    }

    // Save incoming channel message
    suspend fun saveIncomingChannelMessage(
        channel: String,
        content: String,
        senderAddress: Int,
        rssi: Int?,
        snr: Float?
    ): Long {
        val message = Message.channelMessage(
            channel = channel,
            content = content,
            direction = MessageDirection.INCOMING,
            remoteAddress = senderAddress,
            rssi = rssi,
            snr = snr
        )
        return saveMessage(message)
    }

    // Save outgoing channel message
    suspend fun saveOutgoingChannelMessage(channel: String, content: String): Long {
        val message = Message.channelMessage(
            channel = channel,
            content = content,
            direction = MessageDirection.OUTGOING
        )
        return saveMessage(message)
    }

    // Save incoming DM
    suspend fun saveIncomingDm(
        senderAddress: Int,
        content: String,
        rssi: Int?,
        snr: Float?
    ): Long {
        val message = Message.directMessage(
            remoteAddress = senderAddress,
            content = content,
            direction = MessageDirection.INCOMING,
            rssi = rssi,
            snr = snr
        )
        return saveMessage(message)
    }

    // Save outgoing DM
    suspend fun saveOutgoingDm(recipientAddress: Int, content: String): Long {
        val message = Message.directMessage(
            remoteAddress = recipientAddress,
            content = content,
            direction = MessageDirection.OUTGOING
        )
        return saveMessage(message)
    }

    companion object {
        @Volatile
        private var INSTANCE: Repository? = null

        fun getInstance(context: Context): Repository {
            return INSTANCE ?: synchronized(this) {
                val instance = Repository(context.applicationContext)
                INSTANCE = instance
                instance
            }
        }
    }
}
