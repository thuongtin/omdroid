package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

/** The screen for a launch that died: the exit code of this launch, never a stale one (r11 V6.3). */
class FailedLaunchTest {
    private val started = 1_000_000L

    @Test
    fun `a session that died during this launch shows its exit code`() {
        assertEquals(
            FailedLaunchScreen.ExitCode(7),
            FailedLaunch.screen(ReadyReason.SESSION_DIED, 7, started + 900, started),
        )
    }

    @Test
    fun `an exit code from an earlier session is not shown for this launch`() {
        assertEquals(
            FailedLaunchScreen.NotStarted("session_died"),
            FailedLaunch.screen(ReadyReason.SESSION_DIED, 7, started - 1, started),
        )
    }

    @Test
    fun `no exit recorded yet falls back to the reason`() {
        assertEquals(
            FailedLaunchScreen.NotStarted("session_died"),
            FailedLaunch.screen(ReadyReason.SESSION_DIED, Int.MIN_VALUE, 0L, started),
        )
    }

    @Test
    fun `a timeout keeps its own text even when an old exit exists`() {
        assertEquals(
            FailedLaunchScreen.NotStarted("timeout"),
            FailedLaunch.screen(ReadyReason.TIMEOUT, 7, started + 5, started),
        )
    }

    @Test
    fun `a clean exit of this launch is shown as the ended screen too`() {
        assertEquals(
            FailedLaunchScreen.ExitCode(0),
            FailedLaunch.screen(ReadyReason.SESSION_DIED, 0, started, started),
        )
    }
}
