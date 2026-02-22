package com.heronsquawk.app.data

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface MessageDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(message: Message): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(messages: List<Message>)

    @Delete
    suspend fun delete(message: Message)

    @Query("SELECT * FROM messages ORDER BY timestamp DESC")
    fun getAllMessages(): Flow<List<Message>>

    @Query("SELECT * FROM messages WHERE type = :type ORDER BY timestamp DESC")
    fun getMessagesByType(type: MessageType): Flow<List<Message>>

    // Channel messages
    @Query("SELECT * FROM messages WHERE type = 'CHANNEL' AND channel = :channel ORDER BY timestamp ASC")
    fun getChannelMessages(channel: String): Flow<List<Message>>

    @Query("DELETE FROM messages WHERE type = 'CHANNEL' AND channel = :channel")
    suspend fun clearChannelMessages(channel: String)

    // Direct messages
    @Query("SELECT * FROM messages WHERE type = 'DM' AND remoteAddress = :address ORDER BY timestamp ASC")
    fun getDirectMessages(address: Int): Flow<List<Message>>

    @Query("DELETE FROM messages WHERE type = 'DM' AND remoteAddress = :address")
    suspend fun clearDirectMessages(address: Int)

    // Get unique DM addresses (for conversation list)
    @Query("SELECT remoteAddress FROM messages WHERE type = 'DM' AND remoteAddress IS NOT NULL GROUP BY remoteAddress ORDER BY MAX(timestamp) DESC")
    fun getDmAddresses(): Flow<List<Int>>

    // Clear all messages
    @Query("DELETE FROM messages")
    suspend fun clearAll()

    // Get message count
    @Query("SELECT COUNT(*) FROM messages")
    suspend fun getMessageCount(): Int
}
