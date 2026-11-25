package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File

class UiModeTest {

    @TempDir
    lateinit var rootfs: File

    private val modeFile: File
        get() = File(rootfs, UiMode.MODE_PATH)

    private val pinFile: File
        get() = File(rootfs, UiMode.PIN_PATH)

    @Test
    fun `no pin follows the dock state`() {
        assertEquals(UiMode.DESKTOP, UiMode.write(pin = null, current = null, docked = true))
        assertEquals(UiMode.MOBILE, UiMode.write(pin = null, current = null, docked = false))
    }

    @Test
    fun `the default pin is auto even when the file is missing or garbage`() {
        assertEquals(UiMode.AUTO, UiMode.normalisePin(null))
        assertEquals(UiMode.AUTO, UiMode.normalisePin(""))
        assertEquals(UiMode.AUTO, UiMode.normalisePin("Desktop please"))
        assertEquals(UiMode.DESKTOP, UiMode.normalisePin(" desktop\n"))
    }

    @Test
    fun `a pin stops the host writing anything`() {
        assertNull(UiMode.write(pin = "mobile", current = "desktop", docked = true))
        assertNull(UiMode.write(pin = "desktop", current = "mobile", docked = false))
    }

    @Test
    fun `an unchanged mode is not rewritten`() {
        assertNull(UiMode.write(pin = "auto", current = "desktop", docked = true))
        assertNull(UiMode.write(pin = null, current = "mobile", docked = false))
    }

    @Test
    fun `an unknown mode file is replaced by the dock state`() {
        assertEquals(UiMode.DESKTOP, UiMode.write(pin = null, current = "fancy", docked = true))
    }

    @Test
    fun `apply creates the config dir and writes the docked mode`() {
        val outcome = UiModeFile(rootfs).apply(docked = true)

        assertEquals(UiMode.DESKTOP, outcome.written)
        assertEquals(UiMode.DESKTOP, outcome.effective)
        assertEquals("docked", outcome.reason)
        assertEquals("desktop", modeFile.readText().trim())
    }

    @Test
    fun `apply undocks back to mobile`() {
        UiModeFile(rootfs).apply(docked = true)

        val outcome = UiModeFile(rootfs).apply(docked = false)

        assertEquals(UiMode.MOBILE, outcome.written)
        assertEquals("undocked", outcome.reason)
        assertEquals("mobile", modeFile.readText().trim())
    }

    @Test
    fun `a second apply with the same dock state writes nothing`() {
        UiModeFile(rootfs).apply(docked = true)
        val stamp = modeFile.lastModified()

        val outcome = UiModeFile(rootfs).apply(docked = true)

        assertNull(outcome.written)
        assertEquals("unchanged", outcome.reason)
        assertEquals(UiMode.DESKTOP, outcome.effective)
        assertEquals(stamp, modeFile.lastModified())
    }

    @Test
    fun `a pinned mode is never overwritten by a dock or an undock`() {
        pinFile.parentFile.mkdirs()
        pinFile.writeText("mobile\n")

        val docked = UiModeFile(rootfs).apply(docked = true)
        val undocked = UiModeFile(rootfs).apply(docked = false)

        assertNull(docked.written)
        assertNull(undocked.written)
        assertEquals("pinned", docked.reason)
        assertEquals(UiMode.MOBILE, docked.effective)
        assertFalse(modeFile.exists())
    }

    @Test
    fun `a pinned desktop survives an undock`() {
        pinFile.parentFile.mkdirs()
        pinFile.writeText("desktop")
        modeFile.parentFile.mkdirs()
        modeFile.writeText("desktop")

        val outcome = UiModeFile(rootfs).apply(docked = false)

        assertNull(outcome.written)
        assertEquals(UiMode.DESKTOP, outcome.effective)
        assertEquals("desktop", modeFile.readText().trim())
    }

    @Test
    fun `a pin of auto is not a pin`() {
        pinFile.parentFile.mkdirs()
        pinFile.writeText("auto\n")

        val outcome = UiModeFile(rootfs).apply(docked = true)

        assertEquals(UiMode.DESKTOP, outcome.written)
        assertEquals("desktop", modeFile.readText().trim())
    }

    @Test
    fun `a missing mode file is written explicitly on the first start`() {
        val desktop = UiModeFile(rootfs).apply(docked = true)
        assertEquals(UiMode.DESKTOP, desktop.written)

        rootfs.deleteRecursively()
        rootfs.mkdirs()
        val mobile = UiModeFile(rootfs).apply(docked = false)

        assertEquals(UiMode.MOBILE, mobile.written)
        assertEquals(UiMode.MOBILE, mobile.effective)
        assertEquals("undocked", mobile.reason)
        assertEquals("mobile", modeFile.readText().trim())
    }

    @Test
    fun `the written file is one clean line with no temp left behind`() {
        UiModeFile(rootfs).apply(docked = true)

        assertTrue(modeFile.isFile)
        assertEquals(1, modeFile.readLines().size)
        assertEquals(
            listOf("ui"),
            modeFile.parentFile.listFiles()?.map { it.name }?.sorted(),
        )
        assertTrue(modeFile.readText().endsWith("\n"))
    }
}
