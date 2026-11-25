package com.phoshdroid.app

import android.app.Application
import android.content.Intent
import android.content.SharedPreferences
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.preference.PreferenceManager
import com.phoshdroid.app.launch.DisplayLaunch
import com.phoshdroid.app.launch.DockState
import com.phoshdroid.app.launch.DockStatus
import com.phoshdroid.app.launch.DockStatusReader
import com.phoshdroid.app.launch.UiModeFile
import com.phoshdroid.app.proot.ProotService
import java.io.File

/**
 * Process-level dock edge (a1/a2/a4/a7): one `dock:` line per change, the guest's
 * UI mode file, the extra-key bar preference, and — when a session is already
 * running — the X activity re-launched onto the monitor.
 *
 * A `DisplayManager.DisplayListener` registered for the application's lifetime,
 * so a monitor appearing or disappearing is noticed while the X activity is on
 * top (the launcher's own lifecycle callbacks never fire then). Display changes
 * that keep the same shape (refresh rate, HDR, rotation of the phone) are
 * filtered by [signature]; the rest are debounced, because plugging a monitor in
 * produces added + changed + changed.
 *
 * The registration call itself only records and logs the state: the launcher owns
 * the launch decision, and re-launching the X activity on a process start would
 * fight it.
 */
class DockMonitor(
    private val app: Application,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var last: DockStatus? = null
    private var signature: String? = null

    private val pending = Runnable { evaluate("change") }

    private val listener =
        object : DisplayManager.DisplayListener {
            override fun onDisplayAdded(displayId: Int) = schedule()

            override fun onDisplayRemoved(displayId: Int) = schedule()

            override fun onDisplayChanged(displayId: Int) = schedule()
        }

    fun register() {
        if (registered) return
        val manager =
            try {
                app.getSystemService(DisplayManager::class.java)
            } catch (e: Exception) {
                null
            }
        if (manager != null) {
            manager.registerDisplayListener(listener, handler)
            registered = true
        }
        evaluate("start")
    }

    /** Re-reads the dock state now; safe to call from anywhere on the main thread. */
    fun evaluate(reason: String) {
        val status =
            try {
                DockStatusReader.read(app)
            } catch (e: Exception) {
                Log.w(TAG, "dock: state unreadable: ${e.message}")
                return
            }
        val first = last == null
        last = status
        val changed = signature != signatureOf(status)
        signature = signatureOf(status)
        if (!first && !changed) return
        Log.i(TAG, DockState.logLine(status) + if (reason == "start") "" else " ($reason)")
        react(status, relaunch = !first)
    }

    /** The dock state as last observed, or a fresh read when nothing was observed yet. */
    fun status(): DockStatus = last ?: DockStatusReader.read(app)

    private fun schedule() {
        handler.removeCallbacks(pending)
        handler.postDelayed(pending, DEBOUNCE_MS)
    }

    /**
     * [relaunch] is false for the first observation of a process: the launcher is
     * about to decide the launch itself and must not be raced.
     */
    private fun react(
        status: DockStatus,
        relaunch: Boolean,
    ) {
        applyUiMode(status)

        // a7: the extra-key bar is a phone affordance. Hiding it here also removes
        // it from the X root prediction, because LauncherActivity reads the same
        // preferences before it computes one.
        setExtraKeysVisible(!status.docked)

        if (!relaunch) return
        if (!ProotService.isRunning()) return
        if (status.docked) {
            moveSession(status)
        } else {
            // The display is gone; Android migrates its windows to the default
            // display itself. Do not re-launch: that would steal focus from
            // whatever the user is doing on the phone.
            Log.i(TAG, "dock: monitor gone, the session follows to the default display")
        }
    }

    /** a2/b2: the guest's `~/.config/omdroid/ui` for the current dock state, with the pin rule. */
    private fun applyUiMode(status: DockStatus) {
        val rootfs = guestRootfs()
        if (rootfs == null) {
            Log.i(TAG, "dock: ui not written, no guest rootfs yet")
            return
        }
        val outcome =
            try {
                UiModeFile(rootfs).apply(status.docked)
            } catch (e: Exception) {
                Log.w(TAG, "dock: ui write failed: ${e.message}")
                return
            }
        val verb = if (outcome.written != null) "written" else "kept"
        Log.i(TAG, "dock: ui ${outcome.effective} $verb (${outcome.reason})")
    }

    /** a4: put the already-running X activity on the monitor. */
    private fun moveSession(status: DockStatus) {
        val displayId =
            status.launchDisplayId ?: run {
                Log.i(TAG, "dock: display ${status.displayId} is private; open Omdroid on it instead")
                return
            }
        val intent =
            Intent()
                .setClassName(app, X_ACTIVITY)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
                .putExtra("phoshdroid_top_padding_px", 0)
                .putExtra("phoshdroid_bottom_padding_px", 0)
        try {
            val onDisplay = DisplayLaunch.start(app, intent, displayId)
            Log.i(
                TAG,
                if (onDisplay) {
                    "dock: session asked onto display $displayId"
                } else {
                    "dock: session launch fell back to the default display"
                },
            )
        } catch (e: Exception) {
            // No visible window of ours (BAL refusal, or the activity is gone):
            // tapping the icon on the monitor opens it there instead.
            Log.w(TAG, "dock: could not move the session: ${e.message}")
        }
    }

    private fun setExtraKeysVisible(visible: Boolean) {
        val prefs = preferences() ?: return
        val shown = prefs.getBoolean(KEY_SHOW_EXTRA_KEYS, true)
        val visibleFlag = prefs.getBoolean(KEY_EXTRA_KEYS_VISIBLE, true)
        if (shown == visible && visibleFlag == visible) return
        prefs
            .edit()
            .putBoolean(KEY_SHOW_EXTRA_KEYS, visible)
            .putBoolean(KEY_EXTRA_KEYS_VISIBLE, visible)
            .apply()
        Log.i(TAG, "dock: extra-key bar " + if (visible) "shown" else "hidden")
    }

    private fun preferences(): SharedPreferences? =
        try {
            PreferenceManager.getDefaultSharedPreferences(app)
        } catch (e: Exception) {
            null
        }

    private fun guestRootfs(): File? {
        val dir =
            File(
                app.filesDir,
                "usr/var/lib/proot-distro/installed-rootfs/${ProotService.DISTRO_NAME}",
            )
        return if (dir.isDirectory) dir else null
    }

    private fun signatureOf(status: DockStatus): String =
        listOf(
            status.docked,
            status.displayId,
            status.launchDisplayId,
            status.display?.width,
            status.display?.height,
            status.display?.densityDpi,
            status.keyboard,
            status.mouse,
        ).joinToString("|")

    companion object {
        private const val TAG = "Phoshdroid"
        private const val DEBOUNCE_MS = 400L
        private const val X_ACTIVITY = "com.termux.x11.MainActivity"

        /** Termux:X11's own preference keys (TermuxX11's Prefs). */
        const val KEY_SHOW_EXTRA_KEYS = "showAdditionalKbd"
        const val KEY_EXTRA_KEYS_VISIBLE = "additionalKbdVisible"

        /** Set by [register]; guards a second registration in the same process. */
        @Volatile
        private var registered = false
    }
}
