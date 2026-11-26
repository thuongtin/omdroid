package com.phoshdroid.app.launch

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Settings

/**
 * Android's limit on an app's child processes ("phantom processes"), and what this app does about it.
 *
 * Every guest process is a child of the app that Android did not start, so the guest is exactly what the
 * monitor counts. Since Android 12 `PhantomProcessList.trimPhantomProcessesIfNecessary()` kills the
 * surplus when more than `max_phantom_processes` (32, all apps together) exist, youngest first among
 * equals, and `ActivityManagerService.checkExcessivePowerUsage()` kills phantom processes over a CPU
 * budget. A `yay` build or a busy desktop can cross either, and the user sees the desktop's apps die
 * with `signal 9`.
 *
 * What switches it off, by release (AOSP `android12-release`, `android12-qpr3-release`,
 * `android12L-release`, `android14-release`, `android16-release`, read for this round):
 *
 * - Android 11 and older: there is no monitor.
 * - Android 12 (API 31) up to QPR2: no switch at all in the platform. Only
 *   `device_config put activity_manager max_phantom_processes <n>`, which needs `WRITE_DEVICE_CONFIG`
 *   and so adb. `android12-qpr3-release` and every later release carry the switch below.
 * - Android 12 QPR3, 12L (API 32), 13 and later: both kills are skipped when
 *   `FeatureFlagUtils.isEnabled(context, "settings_enable_monitor_phantom_procs")` is false. That reads
 *   `Settings.Global` first, then the system property `[persist.]sys.fflag.override.<flag>`, then the
 *   default `true`; `Boolean.parseBoolean` decides, so any value but `true` switches the monitor off.
 *   The Developer options toggle "Disable child process restrictions" (Android 14+) writes the property
 *   and resets it when Developer options are switched off, which is why the global setting, which wins
 *   over the property and stays, is the better one to write.
 *
 * An app holding `WRITE_SECURE_SETTINGS` (granted once over adb, as `docs/omarchy/tools/install.sh`
 * does for [KeyCapture]) can write that global setting. Without the grant the only honest thing is to
 * tell the user the adb command. The pure rule is [decide]; [apply] does the I/O, logs every action and
 * never throws.
 */
object ProcessLimits {
    /** The `Settings.Global` key behind `FeatureFlagUtils.SETTINGS_ENABLE_MONITOR_PHANTOM_PROCS`. */
    const val SETTING = "settings_enable_monitor_phantom_procs"

    /** The first release with a phantom process monitor (Android 12). */
    const val FIRST_SDK_WITH_MONITOR = 31

    enum class Action {
        /** No monitor on this release, or it is already off. */
        NOTHING_TO_DO,

        /** Write `settings_enable_monitor_phantom_procs=false`. */
        DISABLE,

        /** Cannot write it from here: show the user the adb command. */
        TELL_USER,
    }

    /** What the global setting held when it was read. */
    sealed interface Reading {
        /** The read threw (a `SecurityException`) or the provider answered nothing usable. */
        data object Unreadable : Reading

        /** The key is missing or empty: the platform falls through to its property and then its default (on). */
        data object Unset : Reading

        data class Value(
            val raw: String,
        ) : Reading
    }

    fun reading(raw: String?): Reading = if (raw.isNullOrEmpty()) Reading.Unset else Reading.Value(raw)

    /** `Boolean.parseBoolean`, which is what `FeatureFlagUtils.isEnabled` applies to a non-empty value. */
    fun monitorOn(raw: String): Boolean = raw.equals("true", ignoreCase = true)

    fun decide(
        sdkInt: Int,
        setting: Reading,
        canWriteSecureSettings: Boolean,
    ): Action =
        when {
            sdkInt < FIRST_SDK_WITH_MONITOR -> Action.NOTHING_TO_DO
            setting is Reading.Value && !monitorOn(setting.raw) -> Action.NOTHING_TO_DO
            canWriteSecureSettings -> Action.DISABLE
            else -> Action.TELL_USER
        }

    /** The command to run from a computer, as one line. */
    const val ADB_COMMAND = "adb shell settings put global $SETTING false"

    /** The extra commands Android 12 before QPR3 needs, because it has no such setting. */
    const val ADB_COMMAND_ANDROID_12 =
        "adb shell device_config set_sync_disabled_for_tests persistent && " +
            "adb shell device_config put activity_manager max_phantom_processes 2147483647"

    /** What a person should read when the app cannot do it itself. */
    fun instruction(sdkInt: Int): String {
        val base =
            "Android may stop desktop apps once more than 32 background processes exist. " +
                "Fix it once from a computer with USB debugging on: $ADB_COMMAND"
        return when {
            sdkInt == FIRST_SDK_WITH_MONITOR ->
                "$base . If that changes nothing (an Android 12 build before QPR3 has no such setting), run instead: $ADB_COMMAND_ANDROID_12"
            sdkInt >= 34 ->
                "$base . Or turn on Settings > Developer options > Disable child process restrictions " +
                    "(it resets when Developer options are switched off)."
            else -> base
        }
    }

    /** What [apply] did: the action actually taken, one log line, and a note for the user or null. */
    data class Outcome(
        val action: Action,
        val log: String,
        val userNote: String? = null,
    )

    /**
     * Reads the setting and acts on [decide]. Every read and write is wrapped: a `SecurityException`
     * (or any other failure) is a log line, and a refused write becomes [Action.TELL_USER].
     * [enabled] is the Settings switch; when off nothing is read or written.
     */
    fun apply(
        context: Context,
        enabled: Boolean = true,
        sdkInt: Int = android.os.Build.VERSION.SDK_INT,
    ): Outcome {
        if (!enabled) return Outcome(Action.NOTHING_TO_DO, "phantom-procs sdk=$sdkInt switched off in Settings")
        val resolver = context.contentResolver
        val reading =
            try {
                reading(Settings.Global.getString(resolver, SETTING))
            } catch (e: Exception) {
                Reading.Unreadable
            }
        val canWrite =
            context.checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) ==
                PackageManager.PERMISSION_GRANTED
        val seen = "phantom-procs sdk=$sdkInt setting=${describe(reading)} write-secure-settings=$canWrite"
        return when (decide(sdkInt, reading, canWrite)) {
            Action.NOTHING_TO_DO -> Outcome(Action.NOTHING_TO_DO, "$seen -> nothing to do")
            Action.TELL_USER ->
                Outcome(Action.TELL_USER, "$seen -> tell user: $ADB_COMMAND", instruction(sdkInt))
            Action.DISABLE ->
                try {
                    Settings.Global.putString(resolver, SETTING, "false")
                    val after = reading(Settings.Global.getString(resolver, SETTING))
                    if (after is Reading.Value && !monitorOn(after.raw)) {
                        Outcome(Action.DISABLE, "$seen -> wrote $SETTING=false")
                    } else {
                        Outcome(
                            Action.TELL_USER,
                            "$seen -> write did not stick (read back ${describe(after)}): tell user",
                            instruction(sdkInt),
                        )
                    }
                } catch (e: Exception) {
                    Outcome(
                        Action.TELL_USER,
                        "$seen -> write refused: ${e.javaClass.simpleName}: ${e.message}: tell user",
                        instruction(sdkInt),
                    )
                }
        }
    }

    private fun describe(reading: Reading): String =
        when (reading) {
            Reading.Unreadable -> "unreadable"
            Reading.Unset -> "unset"
            is Reading.Value -> reading.raw
        }
}

/** Names for the `onTrimMemory` levels, so the device round can read why Android asked. */
object MemorySignals {
    fun trimLevelName(level: Int): String =
        when {
            level >= 80 -> "TRIM_MEMORY_COMPLETE"
            level >= 60 -> "TRIM_MEMORY_MODERATE"
            level >= 40 -> "TRIM_MEMORY_BACKGROUND"
            level >= 20 -> "TRIM_MEMORY_UI_HIDDEN"
            level >= 15 -> "TRIM_MEMORY_RUNNING_CRITICAL"
            level >= 10 -> "TRIM_MEMORY_RUNNING_LOW"
            level >= 5 -> "TRIM_MEMORY_RUNNING_MODERATE"
            else -> "UNKNOWN"
        }
}
