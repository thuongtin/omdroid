package com.phoshdroid.app.storage

/**
 * When the guest gets Android storage mounted at `~/Phone` (contract section 10).
 *
 * Three stored modes:
 *  - [AUTO]: share while the app holds all-files access, stay off otherwise. The default.
 *  - [ON]:   always share.
 *  - [OFF]:  never share.
 *
 * AUTO is the default because a bind the app cannot read is worse than no bind: without
 * `MANAGE_EXTERNAL_STORAGE` Android still lists some of `/sdcard` (the app's own dirs and the
 * media collections), so the guest would show a tree whose entries fail to open. A fresh install
 * therefore starts with `~/Phone` empty, and the one action that makes it useful (granting
 * all-files access) also turns the bind on, with no second setting to find.
 */
object ShareRule {
    const val AUTO = "auto"
    const val ON = "on"
    const val OFF = "off"

    /** The tri-state preference key. */
    const val KEY = "bind_sdcard_mode"

    /** The boolean switch older builds wrote; read once and folded into [KEY]. */
    const val LEGACY_KEY = "bind_sdcard"

    fun normalise(stored: String?): String =
        when (stored) {
            ON, OFF -> stored
            else -> AUTO
        }

    /** The effective answer for one session: does the guest get `/sdcard` at `~/Phone`? */
    fun resolve(
        mode: String?,
        allFilesGranted: Boolean,
    ): Boolean =
        when (normalise(mode)) {
            ON -> true
            OFF -> false
            else -> allFilesGranted
        }

    /** An install that used the old boolean switch keeps its choice as an explicit mode. */
    fun fromLegacy(legacy: Boolean?): String? =
        when (legacy) {
            true -> ON
            false -> OFF
            null -> null
        }

    /** The stored mode, with an old boolean switch folded in when the tri-state is absent. */
    fun modeFor(
        storedMode: String?,
        legacy: Boolean?,
    ): String = normalise(storedMode ?: fromLegacy(legacy))
}
