package com.phoshdroid.app.launch

import com.phoshdroid.app.launch.ProcessLimits.Action
import com.phoshdroid.app.launch.ProcessLimits.Reading
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ProcessLimitsTest {
    private val unset = Reading.Unset
    private val on = Reading.Value("true")
    private val off = Reading.Value("false")

    @Test
    fun `Android 11 and older has no monitor`() {
        for (sdk in listOf(28, 29, 30)) {
            assertEquals(Action.NOTHING_TO_DO, ProcessLimits.decide(sdk, unset, canWriteSecureSettings = true), "sdk $sdk")
            assertEquals(Action.NOTHING_TO_DO, ProcessLimits.decide(sdk, unset, canWriteSecureSettings = false), "sdk $sdk")
        }
    }

    @Test
    fun `a monitor that is already off is left alone on every release`() {
        for (sdk in listOf(31, 32, 33, 34, 35, 36)) {
            assertEquals(Action.NOTHING_TO_DO, ProcessLimits.decide(sdk, off, canWriteSecureSettings = true), "sdk $sdk")
            assertEquals(Action.NOTHING_TO_DO, ProcessLimits.decide(sdk, off, canWriteSecureSettings = false), "sdk $sdk")
        }
    }

    @Test
    fun `with the grant a monitor that is on or unset is switched off`() {
        for (sdk in listOf(31, 32, 33, 34, 35, 36)) {
            assertEquals(Action.DISABLE, ProcessLimits.decide(sdk, unset, canWriteSecureSettings = true), "unset sdk $sdk")
            assertEquals(Action.DISABLE, ProcessLimits.decide(sdk, on, canWriteSecureSettings = true), "on sdk $sdk")
        }
    }

    @Test
    fun `without the grant the user is told`() {
        for (sdk in listOf(31, 32, 33, 34, 35, 36)) {
            assertEquals(Action.TELL_USER, ProcessLimits.decide(sdk, unset, canWriteSecureSettings = false), "unset sdk $sdk")
            assertEquals(Action.TELL_USER, ProcessLimits.decide(sdk, on, canWriteSecureSettings = false), "on sdk $sdk")
        }
    }

    @Test
    fun `an unreadable setting is treated as on`() {
        assertEquals(Action.DISABLE, ProcessLimits.decide(34, Reading.Unreadable, canWriteSecureSettings = true))
        assertEquals(Action.TELL_USER, ProcessLimits.decide(34, Reading.Unreadable, canWriteSecureSettings = false))
    }

    @Test
    fun `any value but true switches the platform monitor off, as Boolean parseBoolean does`() {
        assertEquals(Reading.Unset, ProcessLimits.reading(null))
        assertEquals(Reading.Unset, ProcessLimits.reading(""))
        assertEquals(Action.NOTHING_TO_DO, ProcessLimits.decide(34, ProcessLimits.reading("FALSE"), true))
        assertEquals(Action.NOTHING_TO_DO, ProcessLimits.decide(34, ProcessLimits.reading("0"), true))
        assertEquals(Action.DISABLE, ProcessLimits.decide(34, ProcessLimits.reading("TRUE"), true))
    }

    @Test
    fun `the instruction carries the exact adb command on every release`() {
        for (sdk in listOf(31, 32, 33, 34, 36)) {
            assertTrue(
                ProcessLimits.instruction(sdk).contains("adb shell settings put global settings_enable_monitor_phantom_procs false"),
                "sdk $sdk",
            )
        }
    }

    @Test
    fun `Android 12 gets the device_config commands and Android 14 the Developer options toggle`() {
        assertTrue(ProcessLimits.instruction(31).contains("max_phantom_processes 2147483647"))
        assertTrue(ProcessLimits.instruction(34).contains("Disable child process restrictions"))
        assertTrue(!ProcessLimits.instruction(33).contains("Developer options"))
        assertTrue(!ProcessLimits.instruction(32).contains("device_config"))
    }

    @Test
    fun `trim levels get their Android names`() {
        assertEquals("TRIM_MEMORY_RUNNING_MODERATE", MemorySignals.trimLevelName(5))
        assertEquals("TRIM_MEMORY_RUNNING_LOW", MemorySignals.trimLevelName(10))
        assertEquals("TRIM_MEMORY_RUNNING_CRITICAL", MemorySignals.trimLevelName(15))
        assertEquals("TRIM_MEMORY_UI_HIDDEN", MemorySignals.trimLevelName(20))
        assertEquals("TRIM_MEMORY_BACKGROUND", MemorySignals.trimLevelName(40))
        assertEquals("TRIM_MEMORY_MODERATE", MemorySignals.trimLevelName(60))
        assertEquals("TRIM_MEMORY_COMPLETE", MemorySignals.trimLevelName(80))
        assertEquals("UNKNOWN", MemorySignals.trimLevelName(0))
    }
}
