package com.phoshdroid.app.launch

/** What the launcher says when the hand-over gave up. */
sealed interface FailedLaunchScreen {
    /** The guest of this very launch ended with [code]: the ended screen with its exit code. */
    data class ExitCode(
        val code: Int,
    ) : FailedLaunchScreen

    /** Anything else: the "desktop did not start" screen with the readiness [reason]. */
    data class NotStarted(
        val reason: String,
    ) : FailedLaunchScreen
}

/**
 * Picks the screen for a launch that did not reach the desktop.
 *
 * A session that dies at launch (a broken `session.env`, a stale prefix) is reported twice: the
 * service shows the ended screen with the exit code, and the waiting bootstrap then sees
 * [ReadyReason.SESSION_DIED]. The second one used to replace the first with "did not start:
 * session_died", which names no exit code. The exit code wins when it belongs to THIS launch, which
 * is when the exit happened after the launch started.
 */
object FailedLaunch {
    fun screen(
        reason: ReadyReason,
        lastExitCode: Int,
        lastExitAtMs: Long,
        launchStartedAtMs: Long,
    ): FailedLaunchScreen =
        if (reason == ReadyReason.SESSION_DIED &&
            lastExitCode != Int.MIN_VALUE &&
            lastExitAtMs >= launchStartedAtMs
        ) {
            FailedLaunchScreen.ExitCode(lastExitCode)
        } else {
            FailedLaunchScreen.NotStarted(reason.name.lowercase())
        }
}
