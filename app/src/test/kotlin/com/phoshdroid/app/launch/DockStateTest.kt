package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class DockStateTest {

    private fun display(
        id: Int,
        width: Int = 0,
        height: Int = 0,
        dpi: Int = 0,
        isDefault: Boolean = false,
        isPrivate: Boolean = false,
        isPresentation: Boolean = false,
    ) = DisplayInfo(
        id = id,
        isDefault = isDefault,
        isPrivate = isPrivate,
        isPresentation = isPresentation,
        width = width,
        height = height,
        densityDpi = dpi,
    )

    @Test
    fun `the phone alone is undocked`() {
        val status = DockState.decide(listOf(display(0, 1080, 2400, 420, isDefault = true)))

        assertFalse(status.docked)
        assertEquals(0, status.displayId)
        assertNull(status.display)
        assertNull(status.launchDisplayId)
        assertEquals("dock: undocked", DockState.logLine(status))
    }

    @Test
    fun `a 1080p monitor docks and is the target`() {
        val status =
            DockState.decide(
                listOf(
                    display(0, 1080, 2400, 420, isDefault = true),
                    display(2, 1920, 1080, 213),
                ),
            )

        assertTrue(status.docked)
        assertEquals(2, status.displayId)
        assertEquals(2, status.launchDisplayId)
        assertEquals(
            "dock: docked display=2 1920x1080@213 kbd=0 mouse=0",
            DockState.logLine(status),
        )
    }

    @Test
    fun `a 4K monitor keeps its own size and density`() {
        val status =
            DockState.decide(
                listOf(
                    display(0, 1080, 2400, 420, isDefault = true),
                    display(3, 3840, 2160, 320),
                ),
            )

        assertEquals(3, status.launchDisplayId)
        assertEquals(3840, status.display?.width)
        assertEquals(320, status.display?.densityDpi)
        assertEquals(
            "dock: docked display=3 3840x2160@320 kbd=1 mouse=1",
            DockState.logLine(status.copy(keyboard = true, mouse = true)),
        )
    }

    @Test
    fun `a private monitor still docks but is not ours to launch onto`() {
        val status =
            DockState.decide(
                listOf(
                    display(0, 1080, 2400, 420, isDefault = true),
                    display(4, 2560, 1440, 160, isPrivate = true),
                ),
            )

        assertTrue(status.docked)
        assertEquals(4, status.displayId)
        assertNull(status.launchDisplayId)
        assertEquals(
            "dock: docked display=4 2560x1440@160 private kbd=0 mouse=0",
            DockState.logLine(status),
        )
    }

    @Test
    fun `a public display wins over a private one`() {
        val status =
            DockState.decide(
                listOf(
                    display(0, 1080, 2400, 420, isDefault = true),
                    display(5, 1280, 720, 160, isPrivate = true),
                    display(6, 1920, 1080, 160, isPresentation = true),
                ),
            )

        assertEquals(6, status.launchDisplayId)
    }

    @Test
    fun `two public monitors resolve to the lowest id`() {
        val status =
            DockState.decide(
                listOf(
                    display(0, 1080, 2400, 420, isDefault = true),
                    display(7, 1920, 1080, 160),
                    display(3, 1920, 1200, 160),
                ),
            )

        assertEquals(3, status.displayId)
    }

    @Test
    fun `input presence is reported but never docks by itself`() {
        val status =
            DockState.decide(
                displays = listOf(display(0, 1080, 2400, 420, isDefault = true)),
                inputs = InputPresence(keyboard = true, mouse = true),
            )

        assertFalse(status.docked)
        assertTrue(status.keyboard)
        assertTrue(status.mouse)
    }

    @Test
    fun `desk mode without a display does not flip the phone`() {
        val status =
            DockState.decide(
                displays = listOf(display(0, 1080, 2400, 420, isDefault = true)),
                deskMode = true,
            )

        assertFalse(status.docked)
        assertTrue(status.deskMode)
    }

    @Test
    fun `desk mode with a monitor reports both`() {
        val status =
            DockState.decide(
                displays = listOf(display(0, 1080, 2400, 420, isDefault = true), display(2, 1920, 1080, 160)),
                deskMode = true,
            )

        assertTrue(status.docked)
        assertTrue(status.deskMode)
    }

    @Test
    fun `no displays at all is undocked`() {
        val status = DockState.decide(emptyList())

        assertFalse(status.docked)
        assertEquals(DockState.DEFAULT_DISPLAY, status.displayId)
        assertEquals("dock: undocked", DockState.logLine(status))
    }
}
