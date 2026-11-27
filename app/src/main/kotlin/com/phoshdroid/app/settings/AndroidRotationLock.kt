package com.phoshdroid.app.settings

import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.view.Surface

/** The embedded display already persists and reapplies these forceOrientation values. */
object AndroidRotationLock {
    /**
     * `Settings.System.ACCELEROMETER_ROTATION` values: 0 freezes the display, 1 follows the
     * sensor. The platform's own rotation lock writes the same switch.
     */
    const val SETTING_LOCKED = 0
    const val SETTING_AUTO = 1

    fun locked(preference: String?): Boolean? = when (preference) {
        "auto" -> false
        "portrait", "landscape", "reverse portrait", "reverse landscape" -> true
        else -> null
    }

    /** A read auto-rotate switch as locked/auto; an unreadable or odd value is unknown. */
    fun lockedFromSetting(setting: Int?): Boolean? = when (setting) {
        SETTING_LOCKED -> true
        SETTING_AUTO -> false
        else -> null
    }

    /**
     * The tile's two mechanisms combined: the display is locked when the platform's auto-rotate
     * switch is off, or when the activity holds a fixed orientation. False needs both readings to
     * say so, and anything else is unknown - never a guessed false.
     */
    fun combinedLocked(setting: Boolean?, preference: Boolean?): Boolean? = when {
        setting == true || preference == true -> true
        setting == false && preference == false -> false
        else -> null
    }

    /**
     * Applies [value] through [write] and trusts it only when [read] comes back with the same
     * value. A write Android refuses (a SecurityException while the WRITE_SETTINGS app-op is
     * missing) is a failure, and so is one Android silently ignores: the read-back is the only
     * proof, so a caller can never report a lock the platform did not take.
     */
    fun applyAndConfirm(
        value: Int,
        write: (Int) -> Unit,
        read: () -> Int?,
    ): Result<Int> =
        try {
            write(value)
            val observed = read()
            if (observed == value) {
                Result.success(value)
            } else {
                Result.failure(IllegalStateException("auto-rotate read $observed after writing $value"))
            }
        } catch (error: Exception) {
            Result.failure(error)
        }

    /** Match Android's natural-display and reverseDefaultRotation conventions. */
    fun currentPreference(orientation: Int, rotation: Int, reverseDefaultRotation: Boolean): String? {
        if (rotation !in Surface.ROTATION_0..Surface.ROTATION_270) return null
        val landscape = when (orientation) {
            Configuration.ORIENTATION_LANDSCAPE -> true
            Configuration.ORIENTATION_PORTRAIT -> false
            else -> return null
        }
        val quarterTurn = rotation == Surface.ROTATION_90 || rotation == Surface.ROTATION_270
        val naturalLandscape = landscape != quarterTurn
        val normalRotation = if (landscape) {
            if (naturalLandscape) Surface.ROTATION_0
            else if (reverseDefaultRotation) Surface.ROTATION_270 else Surface.ROTATION_90
        } else {
            if (!naturalLandscape) Surface.ROTATION_0
            else if (reverseDefaultRotation) Surface.ROTATION_90 else Surface.ROTATION_270
        }
        val name = if (landscape) "landscape" else "portrait"
        return if (rotation == normalRotation) name else "reverse $name"
    }

    fun requestedOrientation(preference: String): Int = when (preference) {
        "portrait" -> ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        "landscape" -> ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        "reverse portrait" -> ActivityInfo.SCREEN_ORIENTATION_REVERSE_PORTRAIT
        "reverse landscape" -> ActivityInfo.SCREEN_ORIENTATION_REVERSE_LANDSCAPE
        else -> ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
    }
}
