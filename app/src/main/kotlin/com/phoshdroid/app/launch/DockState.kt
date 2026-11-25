package com.phoshdroid.app.launch

/** One display, as the dock decision sees it (a1). */
data class DisplayInfo(
    val id: Int,
    val isDefault: Boolean,
    val isPrivate: Boolean,
    val isPresentation: Boolean,
    val width: Int,
    val height: Int,
    val densityDpi: Int,
)

/** The input devices Android reports, for the dock log line. */
data class InputPresence(
    val keyboard: Boolean = false,
    val mouse: Boolean = false,
)

/**
 * The dock state at one moment.
 *
 * [displayId] is where the desktop should be drawn: the external display when
 * docked, else [DockState.DEFAULT_DISPLAY]. [launchDisplayId] is the value to
 * hand `ActivityOptions.setLaunchDisplayId`, and is null when the target is not
 * ours to launch onto (a private display, or no external display at all): the
 * caller then launches the way it always has.
 *
 * [deskMode] is Android's `Configuration.UI_MODE_TYPE_DESK`. It is reported for
 * the log and for the report only; it never decides [docked] on its own, because
 * a plain charging dock sets it too and flipping the phone's UI to the desktop
 * layout with no monitor attached would be a regression (see the round report).
 */
data class DockStatus(
    val docked: Boolean,
    val displayId: Int,
    val display: DisplayInfo?,
    val launchDisplayId: Int?,
    val keyboard: Boolean,
    val mouse: Boolean,
    val deskMode: Boolean,
)

/**
 * The dock decision (a1), pure: displays in, docked/undocked and the target
 * display out. The Android edge that feeds it lives in `DockStatusReader`; the
 * unit tests drive this object with dummy displays.
 *
 * A display counts as external when it is not [DockStatus.displayId]'s default
 * display. Public presentation displays win over private ones, then the lowest
 * id, so a simulated secondary display, a USB-C monitor and a DeX desktop all
 * resolve to one id deterministically.
 */
object DockState {
    /** `Display.DEFAULT_DISPLAY`; mirrors the platform constant without depending on it. */
    const val DEFAULT_DISPLAY = 0

    fun decide(
        displays: List<DisplayInfo>,
        inputs: InputPresence = InputPresence(),
        deskMode: Boolean = false,
    ): DockStatus {
        val external =
            displays
                .filter { !it.isDefault }
                .sortedWith(
                    compareByDescending<DisplayInfo> { it.isPresentation }
                        .thenByDescending { !it.isPrivate }
                        .thenBy { it.id },
                ).firstOrNull()
        if (external == null) {
            return DockStatus(
                docked = false,
                displayId = DEFAULT_DISPLAY,
                display = null,
                launchDisplayId = null,
                keyboard = inputs.keyboard,
                mouse = inputs.mouse,
                deskMode = deskMode,
            )
        }
        return DockStatus(
            docked = true,
            displayId = external.id,
            display = external,
            launchDisplayId = if (external.isPrivate) null else external.id,
            keyboard = inputs.keyboard,
            mouse = inputs.mouse,
            deskMode = deskMode,
        )
    }

    /**
     * The one line the device round greps: `dock: docked display=2 1920x1080@213
     * kbd=1 mouse=1`, or `dock: undocked`. A private target adds ` private` so a
     * refusal to launch on it is visible next to the id.
     */
    fun logLine(status: DockStatus): String {
        val display = status.display ?: return "dock: undocked"
        val private = if (display.isPrivate) " private" else ""
        val kbd = if (status.keyboard) 1 else 0
        val mouse = if (status.mouse) 1 else 0
        return "dock: docked display=${display.id} ${display.width}x${display.height}" +
            "@${display.densityDpi}$private kbd=$kbd mouse=$mouse"
    }
}
