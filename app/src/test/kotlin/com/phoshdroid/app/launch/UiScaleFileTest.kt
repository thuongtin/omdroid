package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File

/** F6: the scale the host resolves for the display, and the file the guest follows. */
class UiScaleFileTest {
    @TempDir
    lateinit var rootfs: File

    private val file: File
        get() = File(rootfs, UiScaleFile.PATH)

    private fun display(
        w: Int,
        h: Int,
        dpi: Int,
        isDefault: Boolean = false,
    ) = DisplayInfo(1, isDefault, isPrivate = false, isPresentation = true, width = w, height = h, densityDpi = dpi)

    @Test
    fun `the tablet panel resolves to 2 and a 1080p monitor at 160 dpi to 1`() {
        assertEquals(2, UiScale.forDisplay("auto", display(3200, 2136, 352, isDefault = true)))
        assertEquals(1, UiScale.forDisplay("auto", display(1920, 1080, 160)))
    }

    @Test
    fun `a stored 1 or 2 wins over the display`() {
        assertEquals(2, UiScale.forDisplay("2", display(1920, 1080, 160)))
        assertEquals(1, UiScale.forDisplay("1", display(3200, 2136, 352, isDefault = true)))
    }

    @Test
    fun `an unknown display leaves the file alone`() {
        assertNull(UiScale.forDisplay("auto", null))
        assertNull(UiScale.forDisplay("auto", display(0, 0, 160)))
        assertNull(UiScale.forDisplay("auto", display(1920, 1080, 0)))
    }

    @Test
    fun `only 1 and 2 parse`() {
        assertEquals(1, UiScale.parse("1\n"))
        assertEquals(2, UiScale.parse(" 2 "))
        assertNull(UiScale.parse("1.5"))
        assertNull(UiScale.parse("3"))
        assertNull(UiScale.parse(""))
        assertNull(UiScale.parse(null))
    }

    @Test
    fun `the file is created, rewritten only on a change, and read back`() {
        val scale = UiScaleFile(rootfs)
        assertNull(scale.current())
        assertTrue(scale.apply(2).written)
        assertEquals("2\n", file.readText())
        assertFalse(scale.apply(2).written)
        assertTrue(scale.apply(1).written)
        assertEquals(1, scale.current())
        assertFalse(File(file.parentFile, "ui-scale.tmp").exists())
    }

    @Test
    fun `a garbage file counts as unset and is replaced`() {
        file.parentFile.mkdirs()
        file.writeText("auto\n")
        val scale = UiScaleFile(rootfs)
        assertNull(scale.current())
        assertTrue(scale.apply(1).written)
        assertEquals(1, scale.current())
    }

    @Test
    fun `a scale other than 1 or 2 is refused`() {
        assertThrows(IllegalArgumentException::class.java) { UiScaleFile(rootfs).apply(3) }
        assertFalse(file.exists())
    }

    @Test
    fun `the dock state carries the built-in display for the undocked scale`() {
        val phone = display(3200, 2136, 352, isDefault = true).copy(id = 0)
        val undocked = DockState.decide(listOf(phone))
        assertEquals(phone, undocked.builtin)
        assertFalse(undocked.docked)
        val monitor = display(1920, 1080, 160)
        val docked = DockState.decide(listOf(phone, monitor))
        assertEquals(phone, docked.builtin)
        assertEquals(monitor, docked.display)
        assertNull(DockState.decide(emptyList()).builtin)
    }
}
