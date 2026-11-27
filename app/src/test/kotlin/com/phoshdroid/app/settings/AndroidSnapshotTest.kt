package com.phoshdroid.app.settings

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File
import java.nio.file.Files

class AndroidSnapshotTest {
    @TempDir lateinit var directory: File

    @Test fun `a link at the temporary name cannot redirect the snapshot write`() {
        val victim = File(directory, "victim").also { it.writeText("prefs") }
        Files.createSymbolicLink(File(directory, "state.json.new").toPath(), victim.toPath())
        assertTrue(writeSnapshot(directory, "state.json", """{"schema":2}"""))
        assertEquals("prefs", victim.readText())
        assertEquals("""{"schema":2}""", File(directory, "state.json").readText())
    }

    @Test fun `a bridge directory that is a link is refused`() {
        val real = File(directory, "real").also { it.mkdirs() }
        val link = File(directory, "omdroid-android")
        Files.createSymbolicLink(link.toPath(), real.toPath())
        assertFalse(usableDirectory(link))
        val fresh = File(directory, "fresh")
        assertTrue(usableDirectory(fresh))
        assertTrue(fresh.isDirectory)
    }
}
