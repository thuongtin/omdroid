package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class DisplayGeometryTest {

    @Test
    fun `tablet with two extra-key rows leaves the bar's height below the root`() {
        // Fact 10 from the brief: 3200x2136 window, density 2.2, no cutout.
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 3200,
                windowHeight = 2136,
                density = 2.2f,
                extraKeyRows = 2,
                extraKeysShown = true,
            )

        assertEquals(165, geometry.bottomGap)
        assertEquals(3200, geometry.width)
        assertEquals(1971, geometry.height)
    }

    @Test
    fun `phone with a top cutout keeps the root clear of it`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 1080,
                windowHeight = 2400,
                density = 2.75f,
                extraKeyRows = 2,
                extraKeysShown = true,
                insetTop = 80,
            )

        // round(37.5 * 2.75 * 2) = round(206.25) = 206
        assertEquals(206, geometry.bottomGap)
        assertEquals(1080, geometry.width)
        assertEquals(2400 - 80 - 206, geometry.height)
    }

    @Test
    fun `left and right cutout insets narrow the root`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 2400,
                windowHeight = 1080,
                density = 2.0f,
                extraKeyRows = 2,
                extraKeysShown = false,
                insetLeft = 100,
                insetRight = 100,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(2200, geometry.width)
        assertEquals(1080, geometry.height)
    }

    @Test
    fun `hidden extra keys leave no gap`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 1280,
                windowHeight = 800,
                density = 2.0f,
                extraKeyRows = 2,
                extraKeysShown = false,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(1280, geometry.width)
        assertEquals(800, geometry.height)
    }

    @Test
    fun `non-positive prediction falls back to the window with no gap`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 100,
                windowHeight = 100,
                density = 2.2f,
                extraKeyRows = 2,
                extraKeysShown = true,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(100, geometry.width)
        assertEquals(100, geometry.height)
    }

    @Test
    fun `zero window size is reported as zero rather than negative`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 0,
                windowHeight = 0,
                density = 2.2f,
                extraKeyRows = 2,
                extraKeysShown = true,
            )

        assertEquals(XGeometry(0, 0, 0), geometry)
    }

    @Test
    fun `a 4K monitor predicts its own size, not the phone window`() {
        // a3: the X activity runs full screen on the monitor, so the prediction
        // is the monitor's real size at the monitor's density (320 dpi = 2.0).
        val geometry =
            DisplayGeometry.forDisplay(
                displayWidth = 3840,
                displayHeight = 2160,
                densityDpi = 320,
                extraKeyRows = 2,
                extraKeysShown = false,
            )

        assertEquals(3840, geometry.width)
        assertEquals(2160, geometry.height)
        assertEquals(0, geometry.bottomGap)
    }

    @Test
    fun `a 1080p monitor at 160 dpi gets a half-density gap when the bar is shown`() {
        // Same shape as the launcher's own path, but every number is the
        // monitor's: 37.5 * (160/160) * 2 = 75.
        val geometry =
            DisplayGeometry.forDisplay(
                displayWidth = 1920,
                displayHeight = 1080,
                densityDpi = 160,
                extraKeyRows = 2,
                extraKeysShown = true,
            )

        assertEquals(75, geometry.bottomGap)
        assertEquals(1920, geometry.width)
        assertEquals(1005, geometry.height)
    }

    @Test
    fun `the phone at 420 dpi keeps its own prediction`() {
        val geometry =
            DisplayGeometry.forDisplay(
                displayWidth = 1080,
                displayHeight = 2400,
                densityDpi = 420,
                extraKeyRows = 2,
                extraKeysShown = true,
                insetTop = 80,
            )

        // 37.5 * (420/160) * 2 = 196.875 -> 197
        assertEquals(197, geometry.bottomGap)
        assertEquals(1080, geometry.width)
        assertEquals(2400 - 80 - 197, geometry.height)
    }
}
