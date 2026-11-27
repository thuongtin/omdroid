package com.phoshdroid.app.settings

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File
import java.nio.file.Files

class AndroidControlRequestsTest {
    @TempDir lateinit var directory: File

    @Test fun `only fixed settings pages are accepted`() {
        assertEquals("wifi", AndroidControlRequests.parse("wifi\n"))
        for (input in listOf("intent:evil", "wifi; reboot", "../settings", "volume 100", "x".repeat(100))) {
            assertNull(AndroidControlRequests.parse(input))
        }
    }

    @Test fun `published requests are consumed once and incomplete writes ignored`() {
        File(directory, "a.request").writeText("bluetooth")
        File(directory, "b.new").writeText("wifi")
        val mailbox = AndroidControlRequests(directory)
        assertEquals(listOf("bluetooth"), mailbox.take())
        assertEquals(emptyList<String>(), mailbox.take())
        assertTrue(File(directory, "b.new").exists())
    }

    @Test fun `stale requests are not replayed`() {
        val file = File(directory, "old.request").also { it.writeText("wifi") }
        file.setLastModified(System.currentTimeMillis() - 60_000)
        assertTrue(AndroidControlRequests(directory).take().isEmpty())
        assertFalse(file.exists())
    }

    @Test fun `symbolic links cannot consume another file`() {
        val target = File(directory, "target").also { it.writeText("wifi") }
        Files.createSymbolicLink(File(directory, "link.request").toPath(), target.toPath())
        assertTrue(AndroidControlRequests(directory).take().isEmpty())
        assertEquals("wifi", target.readText())
    }

    @Test fun `only one request is served per cycle and the surplus is deleted`() {
        File(directory, "a.request").writeText("wifi")
        File(directory, "b.request").writeText("bluetooth")
        File(directory, "c.request").writeText("volume")
        val mailbox = AndroidControlRequests(directory)
        assertEquals(listOf("wifi"), mailbox.take())
        // The other two are gone unread: one page per cycle is the whole mailbox's throughput.
        assertFalse(File(directory, "b.request").exists())
        assertFalse(File(directory, "c.request").exists())
        assertEquals(emptyList<String>(), mailbox.take())
    }

    @Test fun `a directory named like a request is removed without being walked out of the tree`() {
        val outside = File(directory.parentFile, "outside").also { it.mkdirs() }
        File(outside, "keep").writeText("data")
        val intruder = File(directory, "x.request")
        Files.createSymbolicLink(intruder.toPath(), outside.toPath())
        val mailbox = AndroidControlRequests(directory)
        File(directory, "a.request").writeText("wifi")
        assertEquals(listOf("wifi"), mailbox.take())
        // The link went, the directory it pointed at and its contents stayed.
        assertFalse(intruder.exists())
        assertTrue(File(outside, "keep").isFile)
    }
}
