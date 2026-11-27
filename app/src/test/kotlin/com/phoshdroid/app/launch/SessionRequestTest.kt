package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test

/** The guest-to-host session request (launch contract, section 10). */
class SessionRequestTest {
    private val now = 1_800_000_000L

    @Test
    fun `each known action parses with a fresh stamp`() {
        assertEquals(SessionAction.STOP, SessionRequest.parse("stop $now\n", now))
        assertEquals(SessionAction.RESTART, SessionRequest.parse("restart $now", now))
        assertEquals(SessionAction.SHUTDOWN, SessionRequest.parse("shutdown ${now - 5}\n", now))
        assertEquals(SessionAction.HOME, SessionRequest.parse("home ${now + 2}\n", now))
    }

    @Test
    fun `an unknown action is dropped`() {
        assertNull(SessionRequest.parse("poweroff $now", now))
        assertNull(SessionRequest.parse("lock $now", now)) // the guest script maps lock to home itself
        assertNull(SessionRequest.parse("", now))
        assertNull(SessionRequest.parse(null, now))
    }

    @Test
    fun `a request without a readable stamp is dropped`() {
        assertNull(SessionRequest.parse("stop", now))
        assertNull(SessionRequest.parse("stop soon", now))
    }

    @Test
    fun `a stale or far-future stamp is dropped so a leftover file cannot end a new session`() {
        assertEquals(SessionAction.STOP, SessionRequest.parse("stop ${now - SessionRequest.MAX_AGE_SECONDS}", now))
        assertNull(SessionRequest.parse("stop ${now - SessionRequest.MAX_AGE_SECONDS - 1}", now))
        assertNull(SessionRequest.parse("stop ${now + SessionRequest.MAX_AGE_SECONDS + 1}", now))
    }

    @Test
    fun `extra whitespace and a trailing newline are fine`() {
        assertEquals(SessionAction.RESTART, SessionRequest.parse("  restart   $now \n\n", now))
    }
}
