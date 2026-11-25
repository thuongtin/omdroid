package com.phoshdroid.app.launch

import android.app.UiModeManager
import android.content.Context
import android.content.res.Configuration
import android.hardware.display.DisplayManager
import android.util.DisplayMetrics
import android.util.Log
import android.view.Display
import android.view.InputDevice

/**
 * The Android edge of the dock decision (a1): reads the displays, the input
 * devices and the UI mode Android reports, and hands them to the pure
 * [DockState.decide]. No decision lives here.
 *
 * Displays: every display, with `isDefault`, `FLAG_PRIVATE` and whether it came
 * from `DISPLAY_CATEGORY_PRESENTATION`, its real pixel size and its own density
 * (`createDisplayContext` so a DeX density override is what the desktop sees).
 *
 * Inputs: physical only — `isExternal && !isVirtual`, an alphabetic keyboard for
 * `keyboard`, `SOURCE_MOUSE` for `mouse`. The same alphabetic-keyboard rule
 * Termux:X11's own external-keyboard detection uses
 * (`TouchInputHandler.java`), so the phone's gpio-keys volume buttons never count.
 */
object DockStatusReader {
    private const val TAG = "Phoshdroid"

    fun read(context: Context): DockStatus =
        DockState.decide(
            displays = readDisplays(context),
            inputs = readInputs(context),
            deskMode = deskMode(context),
        )

    fun readDisplays(context: Context): List<DisplayInfo> {
        val manager =
            try {
                context.getSystemService(DisplayManager::class.java)
            } catch (e: Exception) {
                null
            } ?: return emptyList()
        val presentation =
            try {
                manager.getDisplays(DisplayManager.DISPLAY_CATEGORY_PRESENTATION)
                    .map { it.displayId }
                    .toSet()
            } catch (e: Exception) {
                emptySet()
            }
        return manager.displays.mapNotNull { display ->
            try {
                val real = DisplayMetrics()
                @Suppress("DEPRECATION")
                display.getRealMetrics(real)
                val densityDpi =
                    runCatching {
                        context.createDisplayContext(display).resources.displayMetrics.densityDpi
                    }.getOrNull() ?: real.densityDpi
                DisplayInfo(
                    id = display.displayId,
                    isDefault = display.displayId == Display.DEFAULT_DISPLAY,
                    isPrivate = (display.flags and Display.FLAG_PRIVATE) != 0,
                    isPresentation = display.displayId in presentation,
                    width = real.widthPixels,
                    height = real.heightPixels,
                    densityDpi = densityDpi,
                )
            } catch (e: Exception) {
                Log.w(TAG, "dock: skipped display ${display.displayId}: ${e.message}")
                null
            }
        }
    }

    fun readInputs(context: Context): InputPresence {
        var keyboard = false
        var mouse = false
        try {
            val manager = context.getSystemService(android.hardware.input.InputManager::class.java)
            for (id in manager.inputDeviceIds) {
                val device =
                    try {
                        manager.getInputDevice(id)
                    } catch (e: Exception) {
                        null
                    } ?: continue
                if (device.isVirtual || !device.isExternal) continue
                if (device.supportsSource(InputDevice.SOURCE_KEYBOARD) &&
                    device.keyboardType == InputDevice.KEYBOARD_TYPE_ALPHABETIC
                ) {
                    keyboard = true
                }
                if (device.supportsSource(InputDevice.SOURCE_MOUSE)) mouse = true
            }
        } catch (e: Exception) {
            Log.w(TAG, "dock: input devices unreadable: ${e.message}")
        }
        return InputPresence(keyboard = keyboard, mouse = mouse)
    }

    /**
     * `UI_MODE_TYPE_DESK`. Reported, never acted on by itself (a charging stand
     * sets it too; see [DockStatus]).
     */
    fun deskMode(context: Context): Boolean =
        try {
            context.getSystemService(UiModeManager::class.java)
                ?.currentModeType == Configuration.UI_MODE_TYPE_DESK
        } catch (e: Exception) {
            false
        }
}
