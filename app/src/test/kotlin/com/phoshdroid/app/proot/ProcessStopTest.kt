package com.phoshdroid.app.proot

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Stopping a guest or broker process: bounded, and never on the caller's thread (r11, the session-end ANR). */
class ProcessStopTest {
    /** A process that dies on the signal named by [diesOn] ("none" never dies, like the broker proot on the device). */
    private class Fake(
        private val diesOn: String,
    ) : Stoppable {
        @Volatile private var alive = true
        val calls = mutableListOf<String>()

        override val isAlive: Boolean get() = alive

        override fun destroy() {
            calls += "TERM"
            if (diesOn == "TERM") alive = false
        }

        override fun destroyForcibly() {
            calls += "KILL"
            if (diesOn == "TERM" || diesOn == "KILL") alive = false
        }

        override fun waitFor(ms: Long): Boolean {
            val end = System.nanoTime() + ms * 1_000_000
            while (alive && System.nanoTime() < end) Thread.sleep(5)
            return !alive
        }
    }

    @Test
    fun `a process that already exited is not signalled`() {
        val p = Fake("TERM").also { it.destroy() }
        p.calls.clear()
        assertEquals(StopOutcome.ALREADY_DEAD, ProcessStop.stop(p, 50, 50))
        assertTrue(p.calls.isEmpty())
    }

    @Test
    fun `SIGTERM is enough when the process obeys it`() {
        val p = Fake("TERM")
        assertEquals(StopOutcome.TERMINATED, ProcessStop.stop(p, 200, 200))
        assertEquals(listOf("TERM"), p.calls)
    }

    @Test
    fun `SIGKILL follows when SIGTERM is ignored`() {
        val p = Fake("KILL")
        assertEquals(StopOutcome.KILLED, ProcessStop.stop(p, 60, 200))
        assertEquals(listOf("TERM", "KILL"), p.calls)
    }

    @Test
    fun `a process that survives both is reported, not waited on forever`() {
        val p = Fake("none")
        val t0 = System.nanoTime()
        assertEquals(StopOutcome.SURVIVED, ProcessStop.stop(p, 60, 60))
        val tookMs = (System.nanoTime() - t0) / 1_000_000
        assertTrue(tookMs in 100..2_000, "bounded wait took $tookMs ms")
    }

    @Test
    fun `stopAsync returns at once for a process that never dies and reports the outcome later`() {
        val p = Fake("none")
        val done = CountDownLatch(1)
        var outcome: StopOutcome? = null
        val t0 = System.nanoTime()
        ProcessStop.stopAsync("test-stop", p, 300, 300) {
            outcome = it
            done.countDown()
        }
        val returnedMs = (System.nanoTime() - t0) / 1_000_000
        // The control: the blocking form takes the whole bounded wait (600 ms), so a 100 ms ceiling
        // here can only be met by a call that really does not wait. The R10 service waited forever.
        assertTrue(returnedMs < 100, "stopAsync blocked the caller for $returnedMs ms")
        assertTrue(p.isAlive)
        assertTrue(done.await(3, TimeUnit.SECONDS))
        assertEquals(StopOutcome.SURVIVED, outcome)
        assertEquals(listOf("TERM", "KILL"), p.calls)
    }
}
