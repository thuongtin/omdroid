package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File

class GpuModeTest {
    @TempDir
    lateinit var dir: File

    @Test
    fun `auto picks KGSL when the Adreno node is usable`() {
        assertEquals(GpuMode.KGSL, GpuModeRule.resolve("auto", kgslUsable = true))
    }

    @Test
    fun `auto picks software when the Adreno node is not usable`() {
        assertEquals(GpuMode.SOFTWARE, GpuModeRule.resolve("auto", kgslUsable = false))
    }

    @Test
    fun `a missing or unknown preference means auto`() {
        assertEquals(GpuMode.KGSL, GpuModeRule.resolve(null, kgslUsable = true))
        assertEquals(GpuMode.SOFTWARE, GpuModeRule.resolve(null, kgslUsable = false))
        assertEquals(GpuMode.SOFTWARE, GpuModeRule.resolve("virgl", kgslUsable = false))
        assertEquals(GpuModeRule.AUTO, GpuModeRule.normalise("garbage"))
        assertEquals(GpuModeRule.AUTO, GpuModeRule.normalise(""))
    }

    @Test
    fun `an explicit KGSL choice is honoured even when the probe says no`() {
        assertEquals(GpuMode.KGSL, GpuModeRule.resolve("kgsl", kgslUsable = false))
        assertEquals(GpuMode.KGSL, GpuModeRule.resolve("kgsl", kgslUsable = true))
    }

    @Test
    fun `an explicit software choice is honoured even on an Adreno phone`() {
        assertEquals(GpuMode.SOFTWARE, GpuModeRule.resolve("software", kgslUsable = true))
        assertEquals(GpuMode.SOFTWARE, GpuModeRule.resolve("software", kgslUsable = false))
    }

    @Test
    fun `whitespace around a stored value is ignored`() {
        assertEquals(GpuMode.SOFTWARE, GpuModeRule.resolve(" software\n", kgslUsable = true))
    }

    @Test
    fun `only auto lets the guest change the mode`() {
        assertEquals(GpuModeRule.SOURCE_AUTO, GpuModeRule.source("auto"))
        assertEquals(GpuModeRule.SOURCE_AUTO, GpuModeRule.source(null))
        assertEquals(GpuModeRule.SOURCE_SETTING, GpuModeRule.source("kgsl"))
        assertEquals(GpuModeRule.SOURCE_SETTING, GpuModeRule.source("software"))
    }

    @Test
    fun `the guest values are the lowercase names`() {
        assertEquals("kgsl", GpuMode.KGSL.value)
        assertEquals("software", GpuMode.SOFTWARE.value)
    }

    @Test
    fun `a readable and writable node is usable`() {
        val node = File(dir, "kgsl-3d0").apply { writeText("") }

        assertTrue(GpuModeRule.isKgslUsable(node))
    }

    @Test
    fun `a missing node is not usable`() {
        assertFalse(GpuModeRule.isKgslUsable(File(dir, "kgsl-3d0")))
    }
}
