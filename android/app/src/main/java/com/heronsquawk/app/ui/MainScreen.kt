package com.heronsquawk.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.heronsquawk.app.ble.BleService
import com.heronsquawk.app.data.Repository
import com.heronsquawk.app.ui.components.NavPage
import com.heronsquawk.app.ui.components.NavigationBar
import com.heronsquawk.app.ui.components.TopBar
import com.heronsquawk.app.ui.screens.ChannelsScreen
import com.heronsquawk.app.ui.screens.DeviceScreen
import com.heronsquawk.app.ui.screens.DmScreen
import com.heronsquawk.app.ui.screens.SettingsScreen

@Composable
fun MainScreen(
    bleService: BleService,
    repository: Repository,
    modifier: Modifier = Modifier
) {
    var currentPage by rememberSaveable { mutableStateOf(NavPage.DEVICE) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        // Top bar with app name
        TopBar()

        // Navigation buttons
        NavigationBar(
            currentPage = currentPage,
            onPageSelected = { currentPage = it }
        )

        HorizontalDivider(
            modifier = Modifier.fillMaxWidth(),
            thickness = 1.dp,
            color = MaterialTheme.colorScheme.outline
        )

        // Page content
        when (currentPage) {
            NavPage.DEVICE -> DeviceScreen(
                bleService = bleService,
                modifier = Modifier.weight(1f)
            )
            NavPage.DM -> DmScreen(
                bleService = bleService,
                repository = repository,
                modifier = Modifier.weight(1f)
            )
            NavPage.CHANNELS -> ChannelsScreen(
                bleService = bleService,
                repository = repository,
                modifier = Modifier.weight(1f)
            )
            NavPage.SETTINGS -> SettingsScreen(
                bleService = bleService,
                repository = repository,
                modifier = Modifier.weight(1f)
            )
        }
    }
}
