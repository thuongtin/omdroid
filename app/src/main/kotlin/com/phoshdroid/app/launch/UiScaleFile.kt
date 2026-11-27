package com.phoshdroid.app.launch

import java.io.File

/** What [UiScaleFile.apply] did, for one log line. */
data class UiScaleOutcome(
    /** The scale the guest will read after this call. */
    val effective: Int,
    /** True when this call changed the file. */
    val written: Boolean,
)

/**
 * The effective UI scale the guest follows live (F6), one integer in
 * `<rootfs>/home/omarchy/.config/omdroid/ui-scale`, next to the host-owned `ui`
 * mode file and written the same way (temp file, then rename).
 *
 * The host owns it: it resolves the scale for the display the desktop is on
 * ([UiScale.forDisplay], which already honours the user's `ui_scale` setting) and
 * writes it on a dock change and before a session starts. The guest watcher reads
 * it every poll and puts the monitor on that scale. A guest without the file keeps
 * the start-time `OMARCHY_SCALE`, so an older app build changes nothing.
 */
class UiScaleFile(
    private val rootfsDir: File,
) {
    fun current(): Int? =
        try {
            val file = File(rootfsDir, PATH)
            if (file.isFile) UiScale.parse(file.readText()) else null
        } catch (e: Exception) {
            null
        }

    /** Writes [scale] when the file does not already say so. */
    fun apply(scale: Int): UiScaleOutcome {
        require(scale in 1..2) { "scale must be 1 or 2" }
        if (current() == scale) return UiScaleOutcome(scale, written = false)
        val file = File(rootfsDir, PATH)
        file.parentFile?.mkdirs()
        val tmp = File(file.parentFile, "${file.name}.tmp")
        tmp.writeText("$scale\n")
        if (!tmp.renameTo(file)) {
            file.writeText("$scale\n")
            tmp.delete()
        }
        return UiScaleOutcome(scale, written = true)
    }

    companion object {
        /** Relative to the guest rootfs; `omarchy-watch.py` reads this path. */
        const val PATH = "home/omarchy/.config/omdroid/ui-scale"
    }
}
