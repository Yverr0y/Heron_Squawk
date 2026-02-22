package com.heronsquawk.app

import android.app.Application
import com.heronsquawk.app.ble.BleService
import com.heronsquawk.app.data.Repository

class App : Application() {
    // Lazy initialization of singletons
    val bleService: BleService by lazy { BleService.getInstance(this) }
    val repository: Repository by lazy { Repository.getInstance(this) }

    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    companion object {
        @Volatile
        private var instance: App? = null

        fun getInstance(): App {
            return instance ?: throw IllegalStateException("Application not initialized")
        }
    }
}
