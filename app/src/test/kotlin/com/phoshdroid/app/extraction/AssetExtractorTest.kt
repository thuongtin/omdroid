package com.phoshdroid.app.extraction

import org.apache.commons.compress.archivers.tar.TarArchiveEntry
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream
import org.apache.commons.compress.archivers.tar.TarConstants
import java.util.zip.GZIPOutputStream
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files

class AssetExtractorTest {

    @TempDir
    lateinit var tempDir: File

    private fun createTar(files: Map<String, ByteArray>): ByteArray {
        val baos = ByteArrayOutputStream()
        GZIPOutputStream(baos).use { gz ->
            TarArchiveOutputStream(gz).use { tar ->
                for ((name, content) in files) {
                    val entry = tar.createArchiveEntry(File(name), name)
                    entry.size = content.size.toLong()
                    tar.putArchiveEntry(entry)
                    tar.write(content)
                    tar.closeArchiveEntry()
                }
            }
        }
        return baos.toByteArray()
    }

    private fun createTarWithLinks(
        files: Map<String, ByteArray>,
        links: List<Pair<String, String>>,
        modes: Map<String, Int> = emptyMap()
    ): ByteArray {
        val baos = ByteArrayOutputStream()
        GZIPOutputStream(baos).use { gz ->
            TarArchiveOutputStream(gz).use { tar ->
                for ((name, content) in files) {
                    val entry = TarArchiveEntry(name)
                    entry.mode = modes[name] ?: TarArchiveEntry.DEFAULT_FILE_MODE
                    entry.size = content.size.toLong()
                    tar.putArchiveEntry(entry)
                    tar.write(content)
                    tar.closeArchiveEntry()
                }
                for ((name, linkTarget) in links) {
                    val entry = TarArchiveEntry(name, TarConstants.LF_LINK)
                    entry.linkName = linkTarget
                    tar.putArchiveEntry(entry)
                    tar.closeArchiveEntry()
                }
            }
        }
        return baos.toByteArray()
    }

    @Test
    fun `extracts single file from tar zst`() {
        val content = "hello world".toByteArray()
        val archive = createTar(mapOf("test.txt" to content))

        val extractor = AssetExtractor()
        extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        val extracted = File(tempDir, "test.txt")
        assertTrue(extracted.exists())
        assertEquals("hello world", extracted.readText())
    }

    @Test
    fun `extracts nested directory structure`() {
        val archive = createTar(mapOf(
            "usr/bin/hello" to "#!/bin/sh".toByteArray(),
            "etc/config" to "key=value".toByteArray()
        ))

        val extractor = AssetExtractor()
        extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        assertTrue(File(tempDir, "usr/bin/hello").exists())
        assertEquals("key=value", File(tempDir, "etc/config").readText())
    }

    @Test
    fun `reports progress during extraction`() {
        val largeContent = ByteArray(10_000) { it.toByte() }
        val archive = createTar(mapOf("big.bin" to largeContent))

        val progressValues = mutableListOf<Int>()
        val extractor = AssetExtractor()
        extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir,
            onProgress = { percent -> progressValues.add(percent) }
        )

        assertTrue(progressValues.isNotEmpty())
        assertEquals(100, progressValues.last())
        for (i in 1 until progressValues.size) {
            assertTrue(progressValues[i] >= progressValues[i - 1])
        }
    }

    @Test
    fun `skips extraction if marker file exists`() {
        val archive = createTar(mapOf("test.txt" to "hello".toByteArray()))

        File(tempDir, ".extraction_complete").createNewFile()

        val extractor = AssetExtractor()
        val result = extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        assertFalse(result)
        assertFalse(File(tempDir, "test.txt").exists())
    }

    @Test
    fun `copies a hard link member as a file with the same content`() {
        val content = "elf payload".toByteArray()
        val archive = createTarWithLinks(
            files = mapOf("./usr/bin/ld.bfd" to content),
            links = listOf("./usr/bin/ld" to "./usr/bin/ld.bfd")
        )

        val extractor = AssetExtractor()
        extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        val link = File(tempDir, "usr/bin/ld")
        assertTrue(link.exists())
        assertTrue(Files.isRegularFile(link.toPath()))
        assertFalse(Files.isSymbolicLink(link.toPath()))
        assertArrayEquals(content, link.readBytes())
    }

    @Test
    fun `the copy is independent of its target`() {
        val content = "original bytes".toByteArray()
        val archive = createTarWithLinks(
            files = mapOf("./usr/bin/ld.bfd" to content),
            links = listOf("./usr/bin/ld" to "./usr/bin/ld.bfd")
        )

        val extractor = AssetExtractor()
        extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        File(tempDir, "usr/bin/ld.bfd").writeText("replaced")

        assertEquals("original bytes", File(tempDir, "usr/bin/ld").readText())
    }

    @Test
    fun `keeps the executable bit on a copied hard link`() {
        val archive = createTarWithLinks(
            files = mapOf("./usr/bin/ld.bfd" to "#!/bin/sh\n".toByteArray()),
            links = listOf("./usr/bin/ld" to "./usr/bin/ld.bfd"),
            modes = mapOf("./usr/bin/ld.bfd" to 0b111_101_101)
        )

        val extractor = AssetExtractor()
        extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        assertTrue(File(tempDir, "usr/bin/ld").canExecute())
    }

    @Test
    fun `skips a hard link whose target is missing and still completes`() {
        val archive = createTarWithLinks(
            files = mapOf("etc/hostname" to "guest".toByteArray()),
            links = listOf("./usr/bin/ld" to "./usr/bin/ld.bfd")
        )

        val extractor = AssetExtractor()
        val result = extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        assertTrue(result)
        assertTrue(File(tempDir, ".extraction_complete").exists())
        assertFalse(File(tempDir, "usr/bin/ld").exists())
        assertEquals(1, extractor.skippedLinks)
    }

    @Test
    fun `counts no skipped links for a normal archive`() {
        val archive = createTarWithLinks(
            files = mapOf("./usr/bin/ld.bfd" to "elf payload".toByteArray()),
            links = listOf("./usr/bin/ld" to "./usr/bin/ld.bfd")
        )

        val extractor = AssetExtractor()
        extractor.extract(
            input = ByteArrayInputStream(archive),
            totalBytes = archive.size.toLong(),
            targetDir = tempDir
        )

        assertEquals(0, extractor.skippedLinks)
    }
}
