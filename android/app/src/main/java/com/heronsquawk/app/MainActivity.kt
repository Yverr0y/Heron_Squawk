package com.heronsquawk.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import com.heronsquawk.app.ui.MainScreen
import com.heronsquawk.app.ui.theme.HeronSquawkTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val app = application as App
        val bleService = app.bleService
        val repository = app.repository

        setContent {
            val darkTheme by repository.settings.darkTheme.collectAsState()

            HeronSquawkTheme(darkTheme = darkTheme) {
                MainScreen(
                    bleService = bleService,
                    repository = repository,
                    modifier = Modifier
                        .fillMaxSize()
                        .systemBarsPadding()
                )
            }
        }
    }
}
