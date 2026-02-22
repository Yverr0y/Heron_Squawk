package com.heronsquawk.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = AccentPrimary,
    onPrimary = TextPrimary,
    primaryContainer = AccentPrimary,
    onPrimaryContainer = TextPrimary,

    secondary = AccentSecondary,
    onSecondary = TextPrimary,
    secondaryContainer = BgTertiary,
    onSecondaryContainer = TextPrimary,

    tertiary = AccentSuccess,
    onTertiary = TextPrimary,

    background = BgPrimary,
    onBackground = TextPrimary,

    surface = BgSecondary,
    onSurface = TextPrimary,
    surfaceVariant = BgTertiary,
    onSurfaceVariant = TextPrimary, // Changed from TextSecondary to TextPrimary (White) for contrast

    error = AccentDanger,
    onError = TextPrimary,

    outline = BorderColor,
    outlineVariant = BorderAccent
)

private val LightColorScheme = lightColorScheme(
    primary = AccentPrimary,
    onPrimary = BgPrimaryLight,
    primaryContainer = AccentSecondary,
    onPrimaryContainer = TextPrimaryLight,

    secondary = AccentSecondary,
    onSecondary = TextPrimaryLight,
    secondaryContainer = BgTertiaryLight,
    onSecondaryContainer = TextPrimaryLight,

    tertiary = AccentSuccess,
    onTertiary = BgPrimaryLight,

    background = BgPrimaryLight,
    onBackground = TextPrimaryLight,

    surface = BgSecondaryLight,
    onSurface = TextPrimaryLight,
    surfaceVariant = BgTertiaryLight,
    onSurfaceVariant = TextSecondaryLight,

    error = AccentDanger,
    onError = BgPrimaryLight,

    outline = BorderColorLight,
    outlineVariant = BorderAccentLight
)

@Composable
fun HeronSquawkTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            window.navigationBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}

// Custom color accessors for app-specific colors
object AppColors {
    @Composable
    fun outgoingBubble(darkTheme: Boolean) = if (darkTheme) OutgoingBubble else OutgoingBubbleLight

    @Composable
    fun outgoingBorder(darkTheme: Boolean) = if (darkTheme) OutgoingBorder else OutgoingBorderLight

    @Composable
    fun incomingBubble(darkTheme: Boolean) = if (darkTheme) IncomingBubble else IncomingBubbleLight

    @Composable
    fun incomingBorder(darkTheme: Boolean) = if (darkTheme) IncomingBorder else IncomingBorderLight

    @Composable
    fun textDim(darkTheme: Boolean) = if (darkTheme) TextDim else TextDimLight

    @Composable
    fun bgHover(darkTheme: Boolean) = if (darkTheme) BgHover else BgHoverLight
}
