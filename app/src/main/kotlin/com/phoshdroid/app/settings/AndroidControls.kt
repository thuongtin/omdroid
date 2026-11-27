package com.phoshdroid.app.settings

import android.app.Activity
import android.app.Application
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.database.ContentObserver
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Bundle
import android.os.FileObserver
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.phoshdroid.app.R
import com.phoshdroid.app.launch.DisplayLaunch
import com.termux.x11.MainActivity
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardOpenOption
import java.util.concurrent.ConcurrentHashMap

/**
 * Android owns the radios and the screen. Publish facts and open its user-mediated controls.
 *
 * Nothing here polls. Android pushes every field: a broadcast receiver covers the battery and
 * power saver, a [ConnectivityManager.NetworkCallback] the network transports, and settings
 * observers the radio switches and the auto-rotate switch the platform only publishes through
 * `Settings`. Rotation reads both that switch and the embedded activity's saved preference, with
 * lifecycle and preference listeners. A [FileObserver] covers the guest's request mailbox.
 * Everything runs on the main looper, where the callbacks already arrive: each pass is a handful
 * of local system-service reads, and a pass happens when something changed.
 *
 * The snapshot is rewritten only when a reading changes, or when a reading has aged far enough
 * that the guest would expire it ([AndroidState.REFRESH_MS] under [AndroidState.FIELD_TTL_MS]).
 * Every field carries the time it was observed, which is the liveness rule the guest applies
 * (contract section 13): an idle desktop costs one write every eight seconds instead of one
 * every two, and a host that stops publishing expires field by field without the file being
 * rewritten.
 *
 * The bridge directory is the guest's `/tmp`, so the guest can write it: the snapshot is opened
 * exclusively (a link planted at the temp name cannot redirect the write) and a directory that
 * has itself been replaced by a link turns the bridge off instead of being written through.
 */
class AndroidControls(
    private val context: Context,
    prefix: File,
    private val displayId: Int? = null,
) {
    private val directory = File(prefix, "tmp/omdroid-android")
    private val requestsDirectory = File(directory, "requests")
    private val requests = AndroidControlRequests(requestsDirectory)
    private val state = AndroidState()
    private val main = Handler(Looper.getMainLooper())
    @Volatile private var running = false
    private var scheduled = false
    private var requestObserver: FileObserver? = null
    private var registered = false
    private var lastWarningAt = 0L
    private var lastAction: String? = null
    private var lastActionAt = 0L
    private val application = context.applicationContext as Application
    private var rotationPreferences: SharedPreferences? = null
    private val rotationPreferenceListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == null || key == "forceOrientation") schedule()
    }
    private val lifecycle = object : Application.ActivityLifecycleCallbacks {
        override fun onActivityResumed(activity: Activity) {
            // The first snapshot can precede MainActivity; a resumed/docked activity may use
            // another preference store. Read and rebind on the next main-loop turn.
            if (activity is MainActivity) schedule()
        }
        override fun onActivityDestroyed(activity: Activity) {
            if (activity is MainActivity) schedule()
        }
        override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) { }
        override fun onActivityStarted(activity: Activity) { }
        override fun onActivityPaused(activity: Activity) { }
        override fun onActivityStopped(activity: Activity) { }
        override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) { }
    }

    /** Battery is a sticky broadcast: the last intent delivered is the current reading. */
    private var battery: Intent? = null

    /** Networks Android currently reports, and whether each carries Wi-Fi. */
    private val networks = ConcurrentHashMap<Network, Boolean>()

    /**
     * True once the network callback has reported at all. Registering delivers the networks that
     * already match, so a session with any network is known immediately; until then connectivity
     * is unknown and is published as null, never as "not connected".
     */
    private var networkKnown = false

    /** Re-confirms every reading before the guest's ten-second window closes. */
    private val refresh =
        object : Runnable {
            override fun run() {
                if (!running) return
                publishNow()
                main.postDelayed(this, AndroidState.REFRESH_MS)
            }
        }

    private val receiver =
        object : BroadcastReceiver() {
            override fun onReceive(
                context: Context,
                intent: Intent,
            ) {
                if (intent.action == Intent.ACTION_BATTERY_CHANGED) battery = intent
                schedule()
            }
        }

    private val settingsObserver =
        object : ContentObserver(main) {
            override fun onChange(
                selfChange: Boolean,
                uri: Uri?,
            ) {
                schedule()
            }
        }

    private val networkCallback =
        object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                // Registering an empty request matches every network; the capabilities say which
                // transport each one uses. getAllNetworks() is deprecated as of our minSdk.
                networks[network] =
                    context.getSystemService(ConnectivityManager::class.java)
                        ?.getNetworkCapabilities(network)
                        ?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
                networkKnown = true
                schedule()
            }

            override fun onCapabilitiesChanged(
                network: Network,
                capabilities: NetworkCapabilities,
            ) {
                networks[network] = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                networkKnown = true
                schedule()
            }

            override fun onLost(network: Network) {
                networks.remove(network)
                networkKnown = true
                schedule()
            }
        }

    fun start() {
        if (running) return
        if (!usableDirectory(directory) || !usableDirectory(requestsDirectory)) {
            Log.w("AndroidControls", "Android controls: the bridge directory is a symbolic link; off")
            return
        }
        // Do not replay taps from a previous session.
        requestsDirectory.listFiles()?.forEach { it.delete() }
        networks.clear()
        networkKnown = false
        state.clear()
        running = true
        register()
        watchRequests()
        publishNow()
        main.postDelayed(refresh, AndroidState.REFRESH_MS)
    }

    fun stop() {
        if (!running) return
        running = false
        main.removeCallbacksAndMessages(null)
        scheduled = false
        requestObserver?.stopWatching()
        requestObserver = null
        unregister()
        state.clear()
        File(directory, "state.json").delete()
    }

    private fun register() {
        if (registered) return
        // Marked before the first listener attaches: a step that throws halfway must not leave the
        // listeners already attached for the life of the process. Every unregister() call below is
        // tolerant of a listener that was never attached.
        registered = true
        val filter =
            IntentFilter().apply {
                addAction(Intent.ACTION_BATTERY_CHANGED)
                addAction(PowerManager.ACTION_POWER_SAVE_MODE_CHANGED)
                addAction(WifiManager.WIFI_STATE_CHANGED_ACTION)
            }
        try {
            application.registerActivityLifecycleCallbacks(lifecycle)
            // System broadcasts still reach a receiver that is not exported; another app's may not.
            ContextCompat.registerReceiver(context, receiver, filter, ContextCompat.RECEIVER_NOT_EXPORTED)
            val resolver = context.contentResolver
            for (uri in listOf(
                Settings.Global.getUriFor(Settings.Global.AIRPLANE_MODE_ON),
                Settings.Global.getUriFor(Settings.Global.BLUETOOTH_ON),
                // The rotation tile's switch, so a change made in Android's own Settings is
                // republished without waiting for the eight-second refresh.
                Settings.System.getUriFor(Settings.System.ACCELEROMETER_ROTATION),
                Settings.System.getUriFor(Settings.System.USER_ROTATION),
            )) {
                resolver.registerContentObserver(uri, false, settingsObserver)
            }
            context.getSystemService(ConnectivityManager::class.java)
                ?.registerNetworkCallback(NetworkRequest.Builder().build(), networkCallback)
        } catch (error: Exception) {
            warn("Android controls: could not register the state listeners", error)
        }
    }

    private fun unregister() {
        if (!registered) return
        registered = false
        application.unregisterActivityLifecycleCallbacks(lifecycle)
        rotationPreferences?.unregisterOnSharedPreferenceChangeListener(rotationPreferenceListener)
        rotationPreferences = null
        runCatching { context.unregisterReceiver(receiver) }
        runCatching { context.contentResolver.unregisterContentObserver(settingsObserver) }
        runCatching {
            context.getSystemService(ConnectivityManager::class.java)?.unregisterNetworkCallback(networkCallback)
        }
    }

    /** Watches the guest's mailbox instead of listing it four times a second. */
    private fun watchRequests() {
        val observer =
            object : FileObserver(requestsDirectory, MOVED_TO or CLOSE_WRITE or CREATE) {
                override fun onEvent(
                    event: Int,
                    path: String?,
                ) {
                    if (path?.endsWith(AndroidControlRequests.SUFFIX) != true) return
                    main.post { takeRequest() }
                }
            }
        try {
            observer.startWatching()
            requestObserver = observer
        } catch (error: Exception) {
            warn("Android controls: could not watch the requests directory", error)
        }
    }

    /** Takes at most one request per event: the mailbox is where the rate limit lives. */
    private fun takeRequest() {
        if (!running) return
        // Same rule as the write side: a directory swapped for a link is not followed.
        if (!usableDirectory(requestsDirectory)) return
        val action = requests.take().firstOrNull() ?: return
        openOnce(action)
    }

    /**
     * Opens a page unless the same page was opened inside [REPEAT_MS]: a guest script that keeps
     * asking for one page must not strobe it, and a person's second tap is far slower than this.
     */
    private fun openOnce(action: String) {
        val now = SystemClock.elapsedRealtime()
        if (action == lastAction && now - lastActionAt < REPEAT_MS) return
        lastAction = action
        lastActionAt = now
        open(action)
    }

    /** Coalesces a burst of callbacks into one publish on the next main-loop turn. */
    private fun schedule() {
        if (!running || scheduled) return
        scheduled = true
        main.post {
            scheduled = false
            if (running) publishNow()
        }
    }

    private fun publishNow() {
        // The check `start()` makes is not enough on its own: the guest can replace the directory
        // with a link while the session runs, so every write re-checks it (one lstat).
        if (!usableDirectory(directory)) return
        val now = System.currentTimeMillis()
        if (!state.observe(read(), now)) return
        if (!writeSnapshot(directory, "state.json", state.json(now))) {
            warn("Android controls: could not replace the state snapshot")
        }
    }

    /** One observation of every field. A read that fails is null, never a guessed false. */
    private fun read(): Map<String, Any?> {
        val wifi = context.getSystemService(WifiManager::class.java)
        val power = context.getSystemService(PowerManager::class.java)
        val resolver = context.contentResolver
        val reading = battery
        fun field(read: () -> Any?): Any? = runCatching(read).getOrNull()
        return linkedMapOf(
            "wifiEnabled" to field { wifi?.isWifiEnabled },
            "wifiConnected" to field { wifiConnected(networkKnown, networks.values) },
            // This is the OS radio state, not a scan or the user's paired-device list.
            "bluetoothEnabled" to
                field {
                    when (Settings.Global.getInt(resolver, Settings.Global.BLUETOOTH_ON, -1)) {
                        0 -> false
                        1 -> true
                        else -> null
                    }
                },
            "airplaneMode" to field { Settings.Global.getInt(resolver, Settings.Global.AIRPLANE_MODE_ON) == 1 },
            "rotationLocked" to field { rotationLocked() },
            "powerSave" to field { power?.isPowerSaveMode },
            "batteryPercent" to
                field {
                    val level = reading?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
                    val scale = reading?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
                    if (level >= 0 && scale > 0) (level * 100 / scale).coerceIn(0, 100) else null
                },
            "charging" to field { reading?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)?.let { it != 0 } },
            "full" to
                field {
                    reading?.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                        ?.let { it == BatteryManager.BATTERY_STATUS_FULL }
                },
        )
    }

    private fun open(action: String) {
        if (action == "rotation-lock" || action == "rotation-auto") {
            setRotationLock(action == "rotation-lock")
            return
        }
        val intentAction = when (action) {
            "wifi" -> Settings.ACTION_WIFI_SETTINGS
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "display" -> Settings.ACTION_DISPLAY_SETTINGS
            "rotation" -> Settings.ACTION_AUTO_ROTATE_SETTINGS
            "volume" -> Settings.Panel.ACTION_VOLUME
            "airplane" -> Settings.ACTION_AIRPLANE_MODE_SETTINGS
            "battery" -> Settings.ACTION_BATTERY_SAVER_SETTINGS
            "settings" -> Settings.ACTION_SETTINGS
            else -> return
        }
        try {
            // Docked, open the page on the display the desktop is on (contract section 8), so it
            // is not raised out of sight on the built-in screen. Any refusal falls back to the
            // plain launch inside DisplayLaunch.
            DisplayLaunch.start(context, Intent(intentAction).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), displayId)
        } catch (error: Exception) {
            warn("Android settings page unavailable: $action", error)
            Toast.makeText(context, R.string.android_settings_unavailable, Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * The tile's state, from what Android actually holds: the platform's auto-rotate switch, read
     * back after every write, plus the activity preference the tile also sets. A refused or
     * silently ignored write leaves the switch where it was, so the tile cannot claim a lock the
     * platform did not take.
     */
    private fun rotationLocked(): Boolean? =
        AndroidRotationLock.combinedLocked(
            AndroidRotationLock.lockedFromSetting(readRotationSetting()),
            rotationPreference(),
        )

    /** The auto-rotate switch, or null when it cannot be read: unknown, never a guessed false. */
    private fun readRotationSetting(): Int? =
        try {
            Settings.System.getInt(context.contentResolver, Settings.System.ACCELEROMETER_ROTATION)
        } catch (_: Settings.SettingNotFoundException) {
            null
        }

    /** The activity preference, and the listener that republishes its changes. */
    private fun rotationPreference(): Boolean? {
        val activity = MainActivity.getInstance()?.takeUnless { it.isFinishing || it.isDestroyed }
        val prefs = activity?.let { MainActivity.getPrefs() }
        val current = prefs?.get()
        if (current !== rotationPreferences) {
            rotationPreferences?.unregisterOnSharedPreferenceChangeListener(rotationPreferenceListener)
            rotationPreferences = current
            current?.registerOnSharedPreferenceChangeListener(rotationPreferenceListener)
        }
        return AndroidRotationLock.locked(prefs?.forceOrientation?.get())
    }

    /**
     * The tile's two writes: Android's auto-rotate switch (needs the WRITE_SETTINGS app-op the
     * installer grants) and the activity preference. The switch is written and read back first;
     * when Android refuses or ignores it nothing else is written, the refusal is logged with its
     * reason, and the snapshot stays at the confirmed state - so the tile shows what happened
     * instead of the intent.
     */
    private fun setRotationLock(locked: Boolean) {
        val value = if (locked) AndroidRotationLock.SETTING_LOCKED else AndroidRotationLock.SETTING_AUTO
        val result = AndroidRotationLock.applyAndConfirm(value, ::writeRotationSetting, ::readRotationSetting)
        val error = result.exceptionOrNull()
        if (error != null) {
            warn("rotation lock refused: wanted=$value read=${readRotationSetting()} canWrite=${canWriteSettings()}", error)
            Toast.makeText(context, R.string.android_rotation_unavailable, Toast.LENGTH_SHORT).show()
            schedule()
            return
        }
        setRotationPreference(locked)
        schedule()
    }

    /** Whether the app holds the WRITE_SETTINGS app-op; a failed check is not held. */
    private fun canWriteSettings(): Boolean =
        try {
            Settings.System.canWrite(context)
        } catch (_: Exception) {
            false
        }

    /** Writes the auto-rotate switch; freezing first pins Android to the quarter turn on screen. */
    private fun writeRotationSetting(value: Int) {
        val resolver = context.contentResolver
        if (value == AndroidRotationLock.SETTING_LOCKED) {
            val activity = MainActivity.getInstance()?.takeUnless { it.isFinishing || it.isDestroyed }
            activity?.display?.rotation?.let {
                Settings.System.putInt(resolver, Settings.System.USER_ROTATION, it)
            }
        }
        Settings.System.putInt(resolver, Settings.System.ACCELEROMETER_ROTATION, value)
    }

    /**
     * The activity preference, applied only after the platform switch is confirmed. It keeps
     * Termux:X11's own "Screen orientation" value in step, which the activity reapplies on focus
     * and after a cold start; a failure here leaves the confirmed system switch in place.
     */
    private fun setRotationPreference(locked: Boolean) {
        try {
            val activity = MainActivity.getInstance()?.takeUnless { it.isFinishing || it.isDestroyed }
            val prefs = MainActivity.getPrefs()
            if (activity == null || prefs == null) return
            if (!locked) {
                activity.requestedOrientation = AndroidRotationLock.requestedOrientation("auto")
                prefs.forceOrientation.put("auto")
                return
            }
            // A repeated lock request keeps the first chosen orientation.
            if (AndroidRotationLock.locked(prefs.forceOrientation.get()) == true) return
            val resources = activity.resources
            val reverseId = resources.getIdentifier("config_reverseDefaultRotation", "bool", "android")
            val preference = AndroidRotationLock.currentPreference(
                resources.configuration.orientation,
                checkNotNull(activity.display).rotation,
                reverseId != 0 && resources.getBoolean(reverseId),
            )
            if (preference == null) {
                // The quarter turn is not identifiable: the system switch already holds the
                // display, so leave the preference alone rather than pin a wrong orientation.
                warn("rotation preference not recorded: unknown orientation")
                return
            }
            activity.requestedOrientation = AndroidRotationLock.requestedOrientation(preference)
            prefs.forceOrientation.put(preference)
        } catch (error: Exception) {
            warn("rotation preference not applied", error)
        }
    }

    /** One warning a minute: a failing write or an unavailable page must not flood the log. */
    private fun warn(
        message: String,
        error: Throwable? = null,
    ) {
        val now = SystemClock.elapsedRealtime()
        if (now - lastWarningAt < WARN_INTERVAL_MS) return
        lastWarningAt = now
        Log.w("AndroidControls", message, error)
    }

    private companion object {
        /** The same page twice inside this window is a repeat, not two taps. */
        const val REPEAT_MS = 500L

        /** Log interval while something keeps failing. */
        const val WARN_INTERVAL_MS = 60_000L
    }
}

/**
 * Wi-Fi connectivity as the network callback sees it: true when any reported network carries
 * Wi-Fi, false when the callback has reported networks and none does, and null until it has
 * reported at all - an unknown reading must not be drawn as "not connected" (contract section 13).
 */
internal fun wifiConnected(
    known: Boolean,
    transports: Collection<Boolean>,
): Boolean? = if (known) transports.any { it } else null

/**
 * Writes [body] to `[directory]/[name]` by temp name plus rename, opening the temp file
 * exclusively so a link planted at that name cannot redirect the write at another file.
 * Returns false when the rename failed.
 */
internal fun writeSnapshot(
    directory: File,
    name: String,
    body: String,
): Boolean {
    val temporary = File(directory, "$name.new")
    Files.deleteIfExists(temporary.toPath())
    Files.newOutputStream(temporary.toPath(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
        .use { it.write(body.toByteArray()) }
    return temporary.renameTo(File(directory, name))
}

/**
 * True when [file] is a real directory, not a symbolic link, and exists. The guest can write the
 * bridge tree, so a link at either level would aim everything below it somewhere else; a session
 * that finds one runs without the bridge instead of writing through it.
 */
internal fun usableDirectory(file: File): Boolean {
    if (Files.isSymbolicLink(file.toPath())) return false
    return file.isDirectory || file.mkdirs()
}
