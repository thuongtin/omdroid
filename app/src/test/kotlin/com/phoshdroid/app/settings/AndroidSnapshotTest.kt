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

    @Test fun `a changed reading rewrites the snapshot at once`() {
        val state = AndroidState()
        assertTrue(state.observe(mapOf("wifiEnabled" to true), 1_000))
        assertFalse(state.observe(mapOf("wifiEnabled" to true), 1_100))
        assertTrue(state.observe(mapOf("wifiEnabled" to false), 1_200))
        assertTrue(state.json(1_200).contains("\"wifiEnabled\":false"))
    }

    @Test fun `a settled reading is written once per refresh window, not once per observation`() {
        val state = AndroidState()
        val values = mapOf("wifiEnabled" to true, "batteryPercent" to 76)
        assertTrue(state.observe(values, 10_000))
        // Nothing changed: the next seven seconds of observations write nothing.
        for (at in 10_001L..10_499L) assertFalse(state.observe(values, at))
        assertFalse(state.observe(values, 10_000 + AndroidState.REFRESH_MS - 1))
        // At the refresh window the reading is re-confirmed, so the guest never expires it.
        assertTrue(state.observe(values, 10_000 + AndroidState.REFRESH_MS))
    }

    @Test fun `every field carries the time it was observed`() {
        val state = AndroidState()
        state.observe(mapOf("wifiEnabled" to true), 5_000)
        state.observe(mapOf("wifiEnabled" to true, "powerSave" to false), 6_000)
        val json = state.json(6_500)
        assertTrue(json.startsWith("""{"schema":2,"timestamp":6500,"observed":{"""))
        assertTrue(json.contains("\"wifiEnabled\":5000"))
        assertTrue(json.contains("\"powerSave\":6000"))
        assertTrue(json.contains("\"wifiEnabled\":true"))
        assertTrue(json.contains("\"powerSave\":false"))
    }

    @Test fun `a failed read is published as null, never as false`() {
        val state = AndroidState()
        state.observe(mapOf("bluetoothEnabled" to null, "batteryPercent" to 76), 1_000)
        assertEquals("""{"schema":2,"timestamp":1000,"observed":{"bluetoothEnabled":1000,"batteryPercent":1000},"bluetoothEnabled":null,"batteryPercent":76}""", state.json(1_000))
    }

    @Test fun `connectivity is unknown until the network callback has reported`() {
        // Before the callback's first report, "no networks known" is not "not connected".
        assertNull(wifiConnected(known = false, transports = emptyList()))
        assertEquals(false, wifiConnected(known = true, transports = emptyList()))
        assertEquals(false, wifiConnected(known = true, transports = listOf(false)))
        assertEquals(true, wifiConnected(known = true, transports = listOf(false, true)))
    }
}
