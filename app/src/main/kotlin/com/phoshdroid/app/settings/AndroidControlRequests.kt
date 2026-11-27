package com.phoshdroid.app.settings

import java.io.File
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.attribute.BasicFileAttributes

/** A private, bounded mailbox. The guest can request settings pages, never commands or intents. */
class AndroidControlRequests(private val directory: File) {
    fun take(now: Long = System.currentTimeMillis()): List<String> {
        val requests = directory.listFiles()?.filter { it.name.endsWith(".request") }
            ?.sortedBy { it.name }?.take(16) ?: return emptyList()
        return requests.mapNotNull { file ->
            try {
                // The reader's side of the same hazard the writer has: the guest can leave a link
                // at this name. Read the attributes and the bytes without following one.
                val attributes =
                    Files.readAttributes(file.toPath(), BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
                val age = now - file.lastModified()
                if (!attributes.isRegularFile || attributes.size() > 32 || age !in 0..30_000) {
                    null
                } else {
                    // No-follow at open time: the file cannot become a link between the check and the read.
                    val text =
                        Files.newInputStream(file.toPath(), LinkOption.NOFOLLOW_LINKS)
                            .use { it.readBytes().toString(Charsets.UTF_8) }
                    parse(text)
                }
            } catch (error: Exception) {
                null
            } finally {
                // A link goes, its target stays: delete(2) removes the link itself.
                file.delete()
            }
        }
    }

    companion object {
        val actions = setOf("wifi", "bluetooth", "display", "rotation", "volume", "airplane", "battery", "settings")

        fun parse(text: String): String? = text.trim().takeIf { text.length <= 32 && it in actions }
    }
}
