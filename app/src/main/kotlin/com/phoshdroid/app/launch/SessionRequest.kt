package com.phoshdroid.app.launch

/** What the guest may ask the host to do with the session (launch contract, section 10). */
enum class SessionAction {
    /** Logout: end the session and show the session-ended screen. */
    STOP,

    /** Restart: end the session and start a fresh one. */
    RESTART,

    /** Shutdown: end the session and close the app. */
    SHUTDOWN,

    /** Suspend and Lock: hand the screen back to Android; the session keeps running. */
    HOME,
}

/**
 * The guest-to-host session request, pure.
 *
 * The guest's `omdroid-session` writes one line, `<action> <unix-seconds>`, to
 * `<prefix>/tmp/omdroid-host/request` (guest: `/tmp/omdroid-host/request`), by
 * temp name plus rename. The host reads it, deletes it (the guest waits for that
 * as its acknowledgement) and acts. Anything it cannot read as a known action, or
 * a request older than [MAX_AGE_SECONDS] (a file left by a session that died),
 * is dropped, so a stale file can never end a fresh session.
 */
object SessionRequest {
    /** Directory under the prefix; the guest sees it as `/tmp/omdroid-host`. */
    const val DIR = "tmp/omdroid-host"
    const val FILE = "request"
    const val MAX_AGE_SECONDS = 30L

    fun parse(
        text: String?,
        nowSeconds: Long,
    ): SessionAction? {
        val parts = text?.trim()?.split(Regex("\\s+")) ?: return null
        val action =
            when (parts.firstOrNull()) {
                "stop" -> SessionAction.STOP
                "restart" -> SessionAction.RESTART
                "shutdown" -> SessionAction.SHUTDOWN
                "home" -> SessionAction.HOME
                else -> return null
            }
        val stamp = parts.getOrNull(1)?.toLongOrNull() ?: return null
        val age = nowSeconds - stamp
        // A little clock slack in the future is fine; an old stamp is a leftover.
        if (age > MAX_AGE_SECONDS || age < -MAX_AGE_SECONDS) return null
        return action
    }
}
