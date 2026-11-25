package com.phoshdroid.app.launch

import java.io.File

/**
 * How the guest's UI mode follows the dock (a2/b2), and the user's pin.
 *
 * Two files under `<rootfs>/home/omarchy/.config/omdroid/`, the same directory
 * the guest's `omdroid-ui.sh` reads:
 *
 * - `ui` is the mode the guest applies: `mobile` or `desktop`. The host owns it
 *   while the pin is `auto`; the guest's watcher reacts to it live.
 * - `ui-pin` is the user's choice: `auto` (the default when the file is missing
 *   or unreadable), `mobile` or `desktop`. While it names a mode the host never
 *   writes `ui` at all, so a hand-chosen mode survives every dock and undock.
 *
 * The rule the host applies is [write]: docked writes `desktop`, undocked writes
 * `mobile`, and nothing is written when the file already says the right thing or
 * the user pinned a mode. Unreadable means `mobile` for both files, matching
 * `omdroid-ui.sh`'s own default.
 */
object UiMode {
    const val AUTO = "auto"
    const val MOBILE = "mobile"
    const val DESKTOP = "desktop"

    /** Mode file relative to the guest rootfs; `omdroid-ui.sh` reads this path. */
    const val MODE_PATH = "home/omarchy/.config/omdroid/ui"

    /** Pin file relative to the guest rootfs. Missing means [AUTO]. */
    const val PIN_PATH = "home/omarchy/.config/omdroid/ui-pin"

    /** A pin of anything but `mobile`/`desktop` means `auto`. */
    fun normalisePin(raw: String?): String =
        when (raw?.trim()) {
            MOBILE -> MOBILE
            DESKTOP -> DESKTOP
            else -> AUTO
        }

    /** A mode file of anything but `mobile`/`desktop` is unset (the guest uses `mobile`). */
    fun normaliseMode(raw: String?): String? =
        when (raw?.trim()) {
            MOBILE -> MOBILE
            DESKTOP -> DESKTOP
            else -> null
        }

    /**
     * The mode the host must write into `ui`, or null when it must leave the
     * file alone. [pin] and [current] are the two files' contents.
     */
    fun write(
        pin: String?,
        current: String?,
        docked: Boolean,
    ): String? {
        if (normalisePin(pin) != AUTO) return null
        val target = if (docked) DESKTOP else MOBILE
        return if (normaliseMode(current) == target) null else target
    }
}

/** What [UiModeFile.apply] did, for one log line. */
data class UiModeOutcome(
    /** The mode the guest will read: the pin when pinned, else the file, else `mobile`. */
    val effective: String,
    /** The mode written by this call, or null when nothing was written. */
    val written: String?,
    /** `pinned`, `unchanged`, `docked` or `undocked`. */
    val reason: String,
)

/**
 * The two files of [UiMode] in one extracted guest rootfs.
 *
 * Writes are atomic (temp file in the same directory, then rename), so a guest
 * that starts between two host calls never reads a half-written mode, and the
 * directory is created on demand because a fresh image has no `omdroid` dir.
 */
class UiModeFile(
    private val rootfsDir: File,
) {
    fun pin(): String? = read(UiMode.PIN_PATH)

    fun current(): String? = read(UiMode.MODE_PATH)

    /**
     * Applies the dock state. Returns what the guest will read and whether this
     * call changed the file, so the launcher can log one line per start.
     */
    fun apply(docked: Boolean): UiModeOutcome {
        val pin = pin()
        val current = current()
        val written = UiMode.write(pin, current, docked)
        if (written != null) write(UiMode.MODE_PATH, written)
        val effective =
            UiMode.normalisePin(pin).takeIf { it != UiMode.AUTO }
                ?: UiMode.normaliseMode(current)
                ?: UiMode.normaliseMode(written)
                ?: UiMode.MOBILE
        val reason =
            when {
                written != null && docked -> "docked"
                written != null -> "undocked"
                UiMode.normalisePin(pin) != UiMode.AUTO -> "pinned"
                else -> "unchanged"
            }
        return UiModeOutcome(effective, written, reason)
    }

    private fun read(relative: String): String? =
        try {
            val file = File(rootfsDir, relative)
            if (file.isFile) file.readText().trim() else null
        } catch (e: Exception) {
            null
        }

    private fun write(
        relative: String,
        text: String,
    ) {
        val file = File(rootfsDir, relative)
        file.parentFile?.mkdirs()
        val tmp = File(file.parentFile, "${file.name}.tmp")
        tmp.writeText("$text\n")
        if (!tmp.renameTo(file)) {
            // A rename can fail on a filesystem that refuses to replace a file
            // another process holds open; fall back to an in-place write.
            file.writeText("$text\n")
            tmp.delete()
        }
    }
}
