package com.phoshdroid.app.launch

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Settings

/**
 * Switches on Termux:X11's `KeyInterceptor` accessibility service from this app's own code.
 *
 * Android 16 handles the Meta keys itself in `PhoneWindowManager.interceptKeyBeforeDispatching`:
 * a Meta press opens the app drawer and is never delivered, and Meta+Tab / Meta+Esc become
 * recents and back. The only component in front of that policy is an accessibility service asking
 * for `FLAG_REQUEST_FILTER_KEY_EVENTS` — Termux:X11's `KeyInterceptor` — so SUPER only reaches
 * Hyprland once that service is enabled. Enabling it means writing `Settings.Secure`, which needs
 * `WRITE_SECURE_SETTINGS` (granted once over adb), and on Android 13+ the service also has to be
 * allowed past "restricted settings" before it will bind.
 *
 * The submodule's own `KeyInterceptor.launch()` is not the right place for this: it can only be
 * reached from the disabled `LoriePreferences` screen, and its write is a straight overwrite of a
 * setting shared with every other accessibility app. The list merge lives here instead, where it
 * can be unit-tested without Android.
 */
object KeyCapture {
    /** Where the service class lives; the package half is this APK's own package name. */
    private const val SERVICE_CLASS = "com.termux.x11.utils.KeyInterceptor"

    /** What [enable] managed to do, for the `launch: key-capture <result>` log line. */
    sealed class Outcome(
        val detail: String,
    ) {
        class Enabled(
            component: String,
        ) : Outcome("enabled $component")

        class NotEnabled(
            detail: String,
        ) : Outcome(detail)
    }

    /** The flattened component for this APK, e.g. `com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor`. */
    fun component(context: Context): String = "${context.packageName}/$SERVICE_CLASS"

    /**
     * Adds [component] to a colon-separated `enabled_accessibility_services` value, once.
     *
     * Every other entry in that setting belongs to a different app (a password manager, TalkBack,
     * a gesture tool), so they are kept exactly as they are and in their order; an existing
     * [component] is not duplicated. A null or empty value becomes just the component.
     */
    fun withService(
        current: String?,
        component: String,
    ): String {
        if (current.isNullOrEmpty()) return component
        if (current.split(':').any { it == component }) return current
        return "$current:$component"
    }

    /**
     * Writes the service into the enabled list and turns accessibility on, returning what
     * happened. It never throws: a missing grant or a refused write is a log line, not a failed
     * launch, and the desktop then runs with Android's own key handling as before.
     */
    fun enable(context: Context): Outcome {
        val component = component(context)
        if (context.checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return Outcome.NotEnabled(
                "no WRITE_SECURE_SETTINGS (adb shell pm grant ${context.packageName} " +
                    "android.permission.WRITE_SECURE_SETTINGS)",
            )
        }
        return try {
            val resolver = context.contentResolver
            val current =
                Settings.Secure.getString(resolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
            val merged = withService(current, component)
            if (merged != current) {
                Settings.Secure.putString(
                    resolver,
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
                    merged,
                )
            }
            Settings.Secure.putString(resolver, Settings.Secure.ACCESSIBILITY_ENABLED, "1")
            Outcome.Enabled(component)
        } catch (e: Exception) {
            Outcome.NotEnabled("write refused: ${e.javaClass.simpleName}: ${e.message}")
        }
    }
}
