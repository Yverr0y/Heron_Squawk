# Heron Squawk Android App - Architecture Document

## Overview
A Jetpack Compose Android app for controlling Heltec V3.1 mesh devices via BLE.

---

## Navigation Structure

```
┌─────────────────────────────────────────┐
│           HERON SQUAWK                  │  ← Top App Bar (always visible)
├─────────────────────────────────────────┤
│  [Device]  [DM]  [Channels]  [Settings] │  ← Navigation Buttons
├─────────────────────────────────────────┤
│                                         │
│                                         │
│           Page Content Area             │  ← Changes based on selected page
│                                         │
│                                         │
│                                         │
└─────────────────────────────────────────┘
```

---

## Pages/Screens

### 1. Device Page (Default/Home)
**Purpose**: BLE device scanning, connection management, device status

```
┌─────────────────────────────────────────┐
│ Connection Status: [● Connected / ○ Disconnected]
├─────────────────────────────────────────┤
│ Connected Device:                       │
│ ┌─────────────────────────────────────┐ │
│ │ HSQ-1A2B                            │ │
│ │ RSSI: -45 dBm                       │ │
│ │ [Disconnect]                        │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ Available Devices:        [↻ Scan]     │
│ ┌─────────────────────────────────────┐ │
│ │ HSQ-3C4D  •  -52 dBm  [Connect]    │ │
│ │ HSQ-5E6F  •  -68 dBm  [Connect]    │ │
│ │ HSQ-7G8H  •  -71 dBm  [Connect]    │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Features**:
- Scan for BLE devices (filter by HSQ- prefix)
- Show RSSI signal strength
- Connect/disconnect buttons
- Auto-reconnect toggle
- Connection status persists across page navigation

---

### 2. DM Page (Direct Messages)
**Purpose**: Send and receive direct messages to specific addresses

```
┌─────────────────────────────────────────┐
│ Direct Messages                         │
├─────────────────────────────────────────┤
│ To Address: [____] (hex, e.g. 1A2B)    │
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ From: 3C4D  •  -45dB  •  10:32 AM  │ │
│ │ Hello there!                        │ │
│ ├─────────────────────────────────────┤ │
│ │                    To: 3C4D  10:33 │ │
│ │                    Hi! How are you? │ │
│ ├─────────────────────────────────────┤ │
│ │ From: 3C4D  •  -48dB  •  10:35 AM  │ │
│ │ Doing great, thanks!                │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ [Message input...              ] [Send] │
│                        [Clear Chat ❌]  │
└─────────────────────────────────────────┘
```

**Features**:
- Address input field (4-char hex)
- Message history (filtered by selected address)
- Incoming messages: left-aligned, gray bubble
- Outgoing messages: right-aligned, green bubble
- Show RSSI, SNR, timestamp
- Clear chat button (clears DMs for this address)

---

### 3. Channels Page
**Purpose**: Channel-based group messaging

```
┌─────────────────────────────────────────┐
│ Channels                                │
├─────────────────────────────────────────┤
│ Active Channels:                        │
│ ┌─────────────────────────────────────┐ │
│ │ [● Unit 1    ] [Leave]              │ │
│ │ [  Team Alpha] [Leave]              │ │
│ │ [  Emergency ] [Leave]              │ │
│ └─────────────────────────────────────┘ │
│ Join: [____________] [Join]            │
├─────────────────────────────────────────┤
│ Messages on: Unit 1  ▼                  │
│ ┌─────────────────────────────────────┐ │
│ │ 1A2B  •  -52dB  •  10:15 AM        │ │
│ │ Check in everyone                   │ │
│ ├─────────────────────────────────────┤ │
│ │                    You  •  10:16   │ │
│ │                    All clear here  │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ [Message input...              ] [Send] │
│                        [Clear Chat ❌]  │
└─────────────────────────────────────────┘
```

**Features**:
- List of joined channels
- Channel selector dropdown
- Join new channel (text input)
- Leave channel (swipe or button)
- Messages grouped by selected channel
- Clear chat for current channel

---

### 4. Settings Page
**Purpose**: Device configuration, app settings, initialization

```
┌─────────────────────────────────────────┐
│ Settings                                │
├─────────────────────────────────────────┤
│ Device Configuration                    │
│ ┌─────────────────────────────────────┐ │
│ │ Passphrase:                         │ │
│ │ [••••••••••••••••••] [👁]           │ │
│ │                                     │ │
│ │ Device Address: 1A2B (read-only)    │ │
│ │ Firmware: v1.0.0 (read-only)        │ │
│ │                                     │ │
│ │ [Save to Device]                    │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ App Settings                            │
│ ┌─────────────────────────────────────┐ │
│ │ Theme:  [◉ Dark] [○ Light]          │ │
│ │ Auto-reconnect: [✓]                 │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ Actions                                 │
│ ┌─────────────────────────────────────┐ │
│ │ [Clear All Messages]                │ │
│ │ [Disconnect Device]                 │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│                                         │
│         [ 🚀 INITIALIZE DEVICE ]        │  ← Bottom of screen
│                                         │
└─────────────────────────────────────────┘
```

**Features**:
- Passphrase input with show/hide toggle
- Save config to device (CONFIG:SET + CONFIG:SAVE)
- Read-only device info (address, firmware)
- Theme toggle (dark/light)
- Auto-reconnect toggle
- Clear all messages button
- INIT button at bottom (sends INIT command)

---

## Color Theme

### Dark Theme (Default)
```kotlin
// Backgrounds
BgPrimary = #0A0E1A        // Main background
BgSecondary = #111827      // Cards, panels
BgTertiary = #1A2332       // Elevated elements
BgHover = #202938          // Pressed states

// Borders
BorderColor = #2D3748
BorderAccent = #3D4A5C

// Text
TextPrimary = #E4E8F0
TextSecondary = #9CA3AF
TextDim = #6B7280

// Accents
AccentPrimary = #3B82F6    // Blue - buttons, links
AccentSecondary = #60A5FA  // Light blue - hover
AccentWarning = #F59E0B    // Orange - warnings
AccentDanger = #EF4444     // Red - errors, delete

// Messages
OutgoingBubble = #064E3B   // Dark green for sent
OutgoingBorder = #047857
IncomingBubble = #1F2937   // Gray for received
```

### Light Theme
```kotlin
// Backgrounds
BgPrimaryLight = #F8FAFC
BgSecondaryLight = #FFFFFF
BgTertiaryLight = #F1F5F9
BgHoverLight = #E2E8F0

// Borders
BorderColorLight = #E2E8F0
BorderAccentLight = #CBD5E1

// Text
TextPrimaryLight = #1E293B
TextSecondaryLight = #64748B
TextDimLight = #94A3B8
```

---

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   UI Layer  │────▶│  ViewModel  │────▶│ Repository  │
│  (Compose)  │◀────│   (State)   │◀────│   (Data)    │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
            ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
            │  BleService │           │ Room Database│           │SharedPrefs  │
            │  (Native)   │           │  (Messages)  │           │ (Settings)  │
            └─────────────┘           └─────────────┘           └─────────────┘
                    │
                    ▼
            ┌─────────────┐
            │   Heltec    │
            │   Device    │
            └─────────────┘
```

---

## State Management

### Global App State (Singleton)
```kotlin
object AppState {
    val connectionState: StateFlow<ConnectionState>
    val connectedDevice: StateFlow<BluetoothDevice?>
    val isListening: StateFlow<Boolean>
    val channels: StateFlow<List<String>>
}

sealed class ConnectionState {
    object Disconnected : ConnectionState()
    object Scanning : ConnectionState()
    object Connecting : ConnectionState()
    data class Connected(val deviceName: String) : ConnectionState()
    data class Error(val message: String) : ConnectionState()
}
```

### Per-Screen ViewModels
```kotlin
// Each screen has its own ViewModel with screen-specific state
class DeviceViewModel : ViewModel()
class DmViewModel : ViewModel()
class ChannelsViewModel : ViewModel()
class SettingsViewModel : ViewModel()
```

---

## File Structure

```
android/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       └── java/com/heronsquawk/app/
│           │
│           ├── App.kt                     # Application class
│           ├── MainActivity.kt            # Single activity
│           │
│           ├── ble/
│           │   ├── BleService.kt          # Native Android BLE
│           │   ├── Protocol.kt            # Command parsing
│           │   └── ConnectionManager.kt   # Connection state machine
│           │
│           ├── data/
│           │   ├── AppDatabase.kt         # Room database
│           │   ├── Message.kt             # Message entity
│           │   ├── MessageDao.kt          # Database queries
│           │   ├── Settings.kt            # SharedPreferences wrapper
│           │   └── Repository.kt          # Single data repository
│           │
│           ├── ui/
│           │   ├── theme/
│           │   │   ├── Color.kt           # All color definitions
│           │   │   ├── Theme.kt           # Dark/Light theme
│           │   │   └── Type.kt            # Typography
│           │   │
│           │   ├── components/
│           │   │   ├── TopBar.kt          # "Heron Squawk" header
│           │   │   ├── NavigationBar.kt   # Page navigation buttons
│           │   │   ├── MessageBubble.kt   # Chat message bubble
│           │   │   ├── DeviceCard.kt      # BLE device list item
│           │   │   └── ChannelChip.kt     # Channel selector chip
│           │   │
│           │   ├── screens/
│           │   │   ├── DeviceScreen.kt    # + DeviceViewModel
│           │   │   ├── DmScreen.kt        # + DmViewModel
│           │   │   ├── ChannelsScreen.kt  # + ChannelsViewModel
│           │   │   └── SettingsScreen.kt  # + SettingsViewModel
│           │   │
│           │   └── MainScreen.kt          # Navigation host
│           │
│           └── util/
│               └── Extensions.kt          # Helper extensions
│
├── build.gradle.kts                       # Root build file
├── settings.gradle.kts
├── gradle.properties
└── gradle/
    └── wrapper/
        └── gradle-wrapper.properties
```

---

## BLE Connection Lifecycle

```
                    ┌──────────────┐
                    │ Disconnected │
                    └──────┬───────┘
                           │ startScan()
                           ▼
                    ┌──────────────┐
          ┌────────│   Scanning   │────────┐
          │        └──────┬───────┘        │
          │ timeout       │ device found   │ stopScan()
          │               ▼                │
          │        ┌──────────────┐        │
          │        │  Connecting  │        │
          │        └──────┬───────┘        │
          │               │ onConnected    │
          │               ▼                │
          │        ┌──────────────┐        │
          └───────▶│  Connected   │◀───────┘
                   └──────┬───────┘
                          │ disconnect() or
                          │ connection lost
                          ▼
                   ┌──────────────┐
                   │ Disconnected │
                   └──────────────┘
```

**Key BLE Behaviors**:
1. Scan filters by device name prefix "HSQ-"
2. No system pairing required (uses Nordic UART Service)
3. Connection state is global - persists across page navigation
4. Auto-reconnect attempts if enabled and connection drops
5. All BLE operations on background thread via coroutines

---

## Database Schema

### Message Entity
```kotlin
@Entity(tableName = "messages")
data class Message(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    val type: MessageType,        // CHANNEL, DM
    val direction: Direction,     // INCOMING, OUTGOING

    val channel: String?,         // For channel messages
    val remoteAddress: Int?,      // For DMs (hex address as int)

    val content: String,
    val timestamp: Long,

    val rssi: Int?,               // Signal strength (incoming only)
    val snr: Float?               // Signal-to-noise (incoming only)
)

enum class MessageType { CHANNEL, DM }
enum class Direction { INCOMING, OUTGOING }
```

---

## Implementation Order

### Phase 1: Project Foundation
1. Create Android project structure
2. Set up build.gradle.kts files
3. Create theme (colors, typography)
4. Create basic navigation structure

### Phase 2: Data Layer
1. Room database + Message entity
2. Settings (SharedPreferences)
3. Repository singleton

### Phase 3: BLE Layer
1. BleService with native Android BLE
2. Protocol command/response parsing
3. ConnectionManager state machine

### Phase 4: UI Screens
1. MainScreen with navigation
2. DeviceScreen (scan, connect)
3. SettingsScreen (config, theme, INIT)
4. ChannelsScreen (join, leave, messages)
5. DmScreen (address input, messages)

### Phase 5: Polish
1. Error handling and user feedback
2. Loading states
3. Clear chat functionality
4. Theme persistence

---

## Dependencies (Simplified)

```kotlin
dependencies {
    // Core
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")

    // Compose
    implementation(platform("androidx.compose:compose-bom:2024.01.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Navigation
    implementation("androidx.navigation:navigation-compose:2.7.6")

    // ViewModel
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")

    // Room (with KAPT)
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    kapt("androidx.room:room-compiler:2.6.1")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // JSON
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
}
```

**What's NOT included** (to avoid build issues):
- ❌ Hilt (manual DI instead)
- ❌ Nordic BLE Library (native Android BLE)
- ❌ KSP (KAPT for Room only)

---

## Notes

1. **Single Activity Architecture**: One MainActivity hosts all screens via Navigation Compose
2. **No Hilt**: ViewModels created with companion object factories, singletons for services
3. **Native BLE**: Direct use of Android BluetoothGatt API, no third-party libraries
4. **Modern Code**: Targets Android 10+ (API 29), uses current Compose and lifecycle APIs
5. **Theme Persistence**: SharedPreferences stores theme preference, applies on app start
