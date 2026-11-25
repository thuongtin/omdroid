package com.phoshdroid.app.launch

import android.app.ActivityOptions
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log

/**
 * a4: starts the X activity on the display the dock decision picked.
 *
 * `ActivityOptions.setLaunchDisplayId` is public since API 26 and present in the
 * compileSdk 35 jar. It throws when the display is private or the app may not
 * start there, and it is ignored on devices without
 * `FEATURE_ACTIVITIES_ON_SECONDARY_DISPLAYS`, so every failure here falls back to
 * exactly today's launch. Nothing else in the flow depends on the display id: the
 * X server is process-wide and the guest follows the X root either way.
 *
 * A non-Activity caller (the dock monitor) must put `FLAG_ACTIVITY_NEW_TASK` on
 * the intent; an Activity caller need not, and the X activity is `singleTask` in
 * our manifest so no path can create a second instance.
 */
object DisplayLaunch {
    private const val TAG = "Phoshdroid"

    /** The options bundle for [displayId]; separated so a failure is testable by eye. */
    fun options(displayId: Int): Bundle =
        ActivityOptions.makeBasic().setLaunchDisplayId(displayId).toBundle()

    /**
     * Returns true when the activity was launched onto [displayId]. False means
     * the plain launch ran instead: no target, or the platform refused it.
     */
    fun start(
        context: Context,
        intent: Intent,
        displayId: Int?,
    ): Boolean {
        if (displayId == null) {
            context.startActivity(intent)
            return false
        }
        return try {
            context.startActivity(intent, options(displayId))
            true
        } catch (e: SecurityException) {
            Log.w(TAG, "dock: display $displayId refused (${e.message}); launching on the default display", e)
            context.startActivity(intent)
            false
        } catch (e: IllegalArgumentException) {
            // A display id that vanished between the decision and the launch.
            Log.w(TAG, "dock: display $displayId is gone (${e.message}); launching on the default display", e)
            context.startActivity(intent)
            false
        }
    }
}
