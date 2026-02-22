package com.heronsquawk.app.data

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class Settings private constructor(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val _darkTheme = MutableStateFlow(prefs.getBoolean(KEY_DARK_THEME, true))
    val darkTheme: StateFlow<Boolean> = _darkTheme.asStateFlow()

    private val _autoReconnect = MutableStateFlow(prefs.getBoolean(KEY_AUTO_RECONNECT, true))
    val autoReconnect: StateFlow<Boolean> = _autoReconnect.asStateFlow()

    private val _lastDeviceAddress = MutableStateFlow(prefs.getString(KEY_LAST_DEVICE, null))
    val lastDeviceAddress: StateFlow<String?> = _lastDeviceAddress.asStateFlow()

    private val _passphrase = MutableStateFlow(prefs.getString(KEY_PASSPHRASE, null))
    val passphrase: StateFlow<String?> = _passphrase.asStateFlow()

    private val _callSign = MutableStateFlow(prefs.getString(KEY_CALL_SIGN, "") ?: "")
    val callSign: StateFlow<String> = _callSign.asStateFlow()

    fun setDarkTheme(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_DARK_THEME, enabled).apply()
        _darkTheme.value = enabled
    }

    fun setAutoReconnect(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_AUTO_RECONNECT, enabled).apply()
        _autoReconnect.value = enabled
    }

    fun setLastDeviceAddress(address: String?) {
        prefs.edit().putString(KEY_LAST_DEVICE, address).apply()
        _lastDeviceAddress.value = address
    }

    fun setPassphrase(passphrase: String?) {
        prefs.edit().putString(KEY_PASSPHRASE, passphrase).apply()
        _passphrase.value = passphrase
    }

    fun setCallSign(callSign: String) {
        prefs.edit().putString(KEY_CALL_SIGN, callSign).apply()
        _callSign.value = callSign
    }

    companion object {
        private const val PREFS_NAME = "heronsquawk_settings"
        private const val KEY_DARK_THEME = "dark_theme"
        private const val KEY_AUTO_RECONNECT = "auto_reconnect"
        private const val KEY_LAST_DEVICE = "last_device_address"
        private const val KEY_PASSPHRASE = "passphrase"
        private const val KEY_CALL_SIGN = "call_sign"

        @Volatile
        private var INSTANCE: Settings? = null

        fun getInstance(context: Context): Settings {
            return INSTANCE ?: synchronized(this) {
                val instance = Settings(context.applicationContext)
                INSTANCE = instance
                instance
            }
        }
    }
}
