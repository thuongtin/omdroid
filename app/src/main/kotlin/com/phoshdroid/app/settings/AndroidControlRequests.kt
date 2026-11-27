package com.phoshdroid.app.settings

import java.io.File
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.attribute.BasicFileAttributes

/** A private, bounded mailbox. The guest can request settings pages, never commands or intents. */
class AndroidControlRequests(private val directory: File) {
    /**
     * Serves at most one request and deletes the rest, so a looping guest cannot open a page per
     * file it writes: the listing is guest-sized, and the one page it gets is the only one the
     * host acts on per call.
     */
    fun take(now: Long = System.currentTimeMillis()): List<String> {
        val listing = directory.listFiles() ?: return emptyList()
        val candidates = listing.filter { it.name.endsWith(SUFFIX) }.sortedBy { it.name }
        // Bounded per call: the surplus goes, and a mailbox filled faster than it is pruned
        // still costs the host a fixed number of unlinks here.
        candidates.drop(1).take(MAX_DISCARD).forEach { discard(it) }
        val file = candidates.firstOrNull() ?: return emptyList()
        return try {
            // The reader's side of the same hazard the writer has: the guest can leave a link at
            // this name. Read the attributes and the bytes without following one.
            val attributes =
                Files.readAttributes(file.toPath(), BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
            val age = now - file.lastModified()
            if (!attributes.isRegularFile || attributes.size() > MAX_BYTES || age !in 0..MAX_AGE_MS) {
                emptyList()
            } else {
                // No-follow at open time: the file cannot become a link between the check and the read.
                val text =
                    Files.newInputStream(file.toPath(), LinkOption.NOFOLLOW_LINKS)
                        .use { it.readBytes().toString(Charsets.UTF_8) }
                listOfNotNull(parse(text))
            }
        } catch (error: Exception) {
            emptyList()
        } finally {
            // A link goes, its target stays: delete(2) removes the link itself.
            file.delete()
        }
    }

    /** Deletes [file] without following a link: the link goes, whatever it points at stays. */
    private fun discard(file: File) {
        try {
            if (Files.isDirectory(file.toPath(), LinkOption.NOFOLLOW_LINKS)) {
                file.listFiles()?.forEach { discard(it) }
            }
            Files.deleteIfExists(file.toPath())
        } catch (_: Exception) {
            // Left for the next call; a request the host cannot prune is still served one at a time.
        }
    }

    companion object {
        val actions = setOf("wifi", "bluetooth", "display", "rotation", "volume", "airplane", "battery", "settings")

        const val SUFFIX = ".request"

        /** A request is one short word; anything larger is not one. */
        const val MAX_BYTES = 32L

        /** A tap older than this was left by a session that ended; it is dropped, not replayed. */
        const val MAX_AGE_MS = 30_000L

        /** Requests discarded per call, so a flood costs a fixed amount of work each time. */
        private const val MAX_DISCARD = 64

        fun parse(text: String): String? = text.trim().takeIf { text.length <= 32 && it in actions }
    }
}
