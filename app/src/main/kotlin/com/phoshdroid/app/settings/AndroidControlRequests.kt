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
     * host acts on per call. A name that is not a readable request (a directory the guest made, a
     * link, a stale or oversized file) is discarded and the walk goes on to the next one, because
     * `delete(2)` fails on a non-empty directory and leaving it at the head of the sort would
     * wedge the mailbox for the rest of the session.
     */
    fun take(now: Long = System.currentTimeMillis()): List<String> {
        val listing = directory.listFiles() ?: return emptyList()
        val candidates = listing.filter { it.name.endsWith(SUFFIX) }.sortedBy { it.name }
        var index = 0
        // Bounded per call: the guest cannot make the walk or the prune open-ended.
        while (index < candidates.size && index < MAX_WALK) {
            val file = candidates[index++]
            val attributes = attributes(file)
            if (attributes == null || !attributes.isRegularFile) {
                discard(file)
                continue
            }
            val age = now - file.lastModified()
            if (attributes.size() > MAX_BYTES || age !in 0..MAX_AGE_MS) {
                discard(file)
                continue
            }
            // Everything queued behind the served request is surplus: one page per call.
            candidates.drop(index).take(MAX_DISCARD).forEach { discard(it) }
            return try {
                // No-follow at open time: the file cannot become a link between the check and the read.
                val text =
                    Files.newInputStream(file.toPath(), LinkOption.NOFOLLOW_LINKS)
                        .use { it.readBytes().toString(Charsets.UTF_8) }
                listOfNotNull(parse(text))
            } catch (error: Exception) {
                emptyList()
            } finally {
                // A link goes, its target stays: delete(2) removes the link itself.
                file.delete()
            }
        }
        return emptyList()
    }

    /** The file's own attributes, without following a link. Null when it cannot be read. */
    private fun attributes(file: File): BasicFileAttributes? =
        try {
            Files.readAttributes(file.toPath(), BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
        } catch (_: Exception) {
            null
        }

    /**
     * Deletes [file] without following a link: the link goes, whatever it points at stays. The
     * descent stops after [MAX_DEPTH] levels and the deeper entry is left in place: the guest owns
     * that tree and can nest it far past what this stack can walk, and a StackOverflowError is an
     * Error - it would escape every catch here and take the main thread with it.
     */
    private fun discard(
        file: File,
        depth: Int = 0,
    ) {
        try {
            if (depth < MAX_DEPTH && Files.isDirectory(file.toPath(), LinkOption.NOFOLLOW_LINKS)) {
                file.listFiles()?.forEach { discard(it, depth + 1) }
            }
            Files.deleteIfExists(file.toPath())
        } catch (_: Exception) {
            // Left for the next call; a request the host cannot prune is still served one at a time.
        }
    }

    companion object {
        val actions = setOf("wifi", "bluetooth", "display", "rotation", "rotation-lock", "rotation-auto", "volume", "airplane", "battery", "settings")

        const val SUFFIX = ".request"

        /** A request is one short word; anything larger is not one. */
        const val MAX_BYTES = 32L

        /** A tap older than this was left by a session that ended; it is dropped, not replayed. */
        const val MAX_AGE_MS = 30_000L

        /** Requests discarded per call, so a flood costs a fixed amount of work each time. */
        private const val MAX_DISCARD = 64

        /** Candidates inspected per call: a directory at the head cannot make the walk unbounded. */
        private const val MAX_WALK = 16

        /** Directory levels the prune descends before it leaves a guest-made tree alone. */
        private const val MAX_DEPTH = 4

        fun parse(text: String): String? = text.trim().takeIf { text.length <= 32 && it in actions }
    }
}
