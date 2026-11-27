package com.phoshdroid.app.proot

/** What stopping a process came to; the log line and the tests read this. */
enum class StopOutcome {
    /** It had already exited. */
    ALREADY_DEAD,

    /** It exited after SIGTERM. */
    TERMINATED,

    /** It exited after SIGKILL. */
    KILLED,

    /** Still alive after SIGKILL and the wait: reported, never papered over. */
    SURVIVED,
}

/** The few calls a stop needs, so a test can stand in for a process that will not die. */
interface Stoppable {
    val isAlive: Boolean

    fun destroy()

    fun destroyForcibly()

    /** Waits up to [ms] for the exit; true when it has exited. */
    fun waitFor(ms: Long): Boolean
}

/**
 * A real process. Signals go to its descendants too ([ProcTree]): a proot that ignores SIGTERM and
 * SIGKILL while its tracee lives has been seen on the device, and it ends once the tracee is gone.
 */
class JavaProcessStoppable(
    private val process: Process,
    private val signalDescendants: (Int, Int) -> Unit = ::signalTree,
) : Stoppable {
    private val pid = ProcTree.pidOf(process)

    override val isAlive: Boolean get() = process.isAlive

    override fun destroy() {
        if (pid > 0) signalDescendants(pid, SIGTERM)
        process.destroy()
    }

    override fun destroyForcibly() {
        if (pid > 0) signalDescendants(pid, SIGKILL)
        process.destroyForcibly()
    }

    override fun waitFor(ms: Long): Boolean = process.waitFor(ms, java.util.concurrent.TimeUnit.MILLISECONDS)

    /** Facts for the log when the process outlives SIGKILL. */
    fun survivorStatus(): String = if (pid > 0) "pid $pid ${ProcTree.status(pid)} children=${ProcTree.descendants(pid)}" else "pid unknown"

    companion object {
        const val SIGTERM = 15
        const val SIGKILL = 9

        private fun signalTree(
            pid: Int,
            signal: Int,
        ) {
            ProcTree.descendants(pid).forEach { android.os.Process.sendSignal(it, signal) }
        }
    }
}

/**
 * Stops a guest or broker process without ever waiting on the caller's thread.
 *
 * The R10 service waited for the fake-root broker with an unbounded `Process.waitFor()` in
 * `onDestroy`, which runs on the main thread. The broker proot did not exit on SIGTERM or SIGKILL
 * on the device (r11 phases 4 and 5), so the main thread stopped for good when a session ended
 * from inside: the launcher never drew its ended screen and Android raised an ANR 5 s later.
 * [stopAsync] puts the whole wait on a named thread; [stop] is the blocking form for a thread that
 * is already off the main thread.
 */
object ProcessStop {
    /** Blocking and bounded: SIGTERM, wait [termWaitMs], SIGKILL, wait [killWaitMs]. Never on the main thread. */
    fun stop(
        process: Stoppable,
        termWaitMs: Long,
        killWaitMs: Long,
    ): StopOutcome {
        if (!process.isAlive) return StopOutcome.ALREADY_DEAD
        process.destroy()
        if (process.waitFor(termWaitMs)) return StopOutcome.TERMINATED
        process.destroyForcibly()
        return if (process.waitFor(killWaitMs)) StopOutcome.KILLED else StopOutcome.SURVIVED
    }

    /** Returns at once; [onDone] runs on the stop thread with the outcome. */
    fun stopAsync(
        name: String,
        process: Stoppable,
        termWaitMs: Long,
        killWaitMs: Long,
        onDone: (StopOutcome) -> Unit,
    ): Thread =
        Thread({
            val outcome =
                try {
                    stop(process, termWaitMs, killWaitMs)
                } catch (_: InterruptedException) {
                    StopOutcome.SURVIVED
                }
            onDone(outcome)
        }, name).apply {
            isDaemon = true
            start()
        }
}
