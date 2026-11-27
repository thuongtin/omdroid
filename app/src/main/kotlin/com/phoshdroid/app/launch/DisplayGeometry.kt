package com.phoshdroid.app.launch

/** The X root size predicted for a hand-over, and the gap left below it. */
data class XGeometry(
    val width: Int,
    val height: Int,
    val bottomGap: Int,
)

/**
 * Predicts the X root size from the Android window it will be shown in
 * (contract section 1), so no resize happens at hand-over.
 *
 * - X width = window width minus the left and right display-cutout insets.
 * - X height = window height minus the top and bottom insets. Nothing is
 *   reserved for the Termux:X11 extra-key bar: since r12 the bar starts hidden
 *   and, with `adjustHeightForEK` off (the default), it is drawn over the X
 *   view instead of shrinking it. [XGeometry.bottomGap] is therefore always 0
 *   and the predicted root fills the window on every display.
 * - There is no top gap either: Termux:X11 runs with `hideCutout=false`, so
 *   Android itself keeps the window clear of a cutout in every rotation.
 * - If the result is not positive, fall back to the window size with no gap.
 *
 * Nothing is rounded to even here; the guest does that for cage's window.
 */
object DisplayGeometry {
    /**
     * The same prediction for the display the X activity will be drawn on (a3):
     * the display's own real metrics, not the launcher's window.
     *
     * A display's real size is what a full-screen, immersive X activity gets, so
     * a 4K monitor predicts 3840x2160 instead of the phone's window. Insets
     * default to 0 because an external display has no cutout; the caller passes
     * the target display's own insets when it has them.
     */
    fun forDisplay(
        displayWidth: Int,
        displayHeight: Int,
        insetLeft: Int = 0,
        insetTop: Int = 0,
        insetRight: Int = 0,
        insetBottom: Int = 0,
    ): XGeometry =
        compute(
            windowWidth = displayWidth,
            windowHeight = displayHeight,
            insetLeft = insetLeft,
            insetTop = insetTop,
            insetRight = insetRight,
            insetBottom = insetBottom,
        )

    fun compute(
        windowWidth: Int,
        windowHeight: Int,
        insetLeft: Int = 0,
        insetTop: Int = 0,
        insetRight: Int = 0,
        insetBottom: Int = 0,
    ): XGeometry {
        val width = windowWidth - insetLeft - insetRight
        val height = windowHeight - insetTop - insetBottom
        if (windowWidth <= 0 || windowHeight <= 0 || width <= 0 || height <= 0) {
            return XGeometry(windowWidth, windowHeight, 0)
        }
        return XGeometry(width, height, 0)
    }
}
