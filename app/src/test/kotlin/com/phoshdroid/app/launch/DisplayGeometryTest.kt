package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class DisplayGeometryTest {

    @Test
    fun `the tablet root fills the window because the key bar no longer reserves space`() {
        // Fact 10 from the r2 brief was 3200x2136 with a 165 px bar gap. Since
        // r12 the Termux:X11 key bar starts hidden and, with adjustHeightForEK
        // off, it is drawn over the X view instead of shrinking it, so the root
        // is the whole window and no gap is reserved.
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 3200,
                windowHeight = 2136,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(3200, geometry.width)
        assertEquals(2136, geometry.height)
    }

    @Test
    fun `phone with a top cutout keeps the root clear of it`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 1080,
                windowHeight = 2400,
                insetTop = 80,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(1080, geometry.width)
        assertEquals(2400 - 80, geometry.height)
    }

    @Test
    fun `left and right cutout insets narrow the root`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 2400,
                windowHeight = 1080,
                insetLeft = 100,
                insetRight = 100,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(2200, geometry.width)
        assertEquals(1080, geometry.height)
    }

    @Test
    fun `no display reserves a gap for the extra-key bar`() {
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 1280,
                windowHeight = 800,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(1280, geometry.width)
        assertEquals(800, geometry.height)
    }

    @Test
    fun `non-positive prediction falls back to the window with no gap`() {
        // The insets alone can now make the prediction non-positive; before r12
        // the extra-key bar was the usual way to get there.
        val geometry =
            DisplayGeometry.compute(
                windowWidth = 100,
                windowHeight = 100,
                insetBottom = 120,
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
            )

        assertEquals(XGeometry(0, 0, 0), geometry)
    }

    @Test
    fun `a 4K monitor predicts its own size, not the phone window`() {
        // a3: the X activity runs full screen on the monitor, so the prediction
        // is the monitor's real size.
        val geometry =
            DisplayGeometry.forDisplay(
                displayWidth = 3840,
                displayHeight = 2160,
            )

        assertEquals(3840, geometry.width)
        assertEquals(2160, geometry.height)
        assertEquals(0, geometry.bottomGap)
    }

    @Test
    fun `a 1080p monitor gets the full root even though the bar can be summoned over it`() {
        // The bar is an overlay: summoning it on a monitor covers the bottom of
        // the desktop, it does not shrink the X root the guest was told about.
        val geometry =
            DisplayGeometry.forDisplay(
                displayWidth = 1920,
                displayHeight = 1080,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(1920, geometry.width)
        assertEquals(1080, geometry.height)
    }

    @Test
    fun `the phone at 420 dpi keeps its own prediction`() {
        val geometry =
            DisplayGeometry.forDisplay(
                displayWidth = 1080,
                displayHeight = 2400,
                insetTop = 80,
            )

        assertEquals(0, geometry.bottomGap)
        assertEquals(1080, geometry.width)
        assertEquals(2400 - 80, geometry.height)
    }
}
