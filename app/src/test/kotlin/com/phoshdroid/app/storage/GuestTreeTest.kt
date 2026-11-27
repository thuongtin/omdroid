package com.phoshdroid.app.storage

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File
import java.nio.file.Files
import java.nio.file.Path

class GuestTreeTest {

    private fun tree(root: Path): GuestTree {
        val rootfs = root.toFile()
        File(rootfs, ".extraction_complete").createNewFile()
        File(rootfs, "home/omarchy/Documents").mkdirs()
        File(rootfs, "home/omarchy/Documents/note.txt").writeText("hello")
        File(rootfs, "home/omarchy/Pictures").mkdirs()
        File(rootfs, "home/omarchy/secret-link-source").mkdirs()
        return GuestTree(rootfs)
    }

    @Test
    fun `resolves a plain path under the home`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        val file = t.resolve("Documents/note.txt")
        assertNotNull(file)
        assertEquals("hello", file!!.readText())
    }

    @Test
    fun `the root itself resolves to the home`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        assertEquals(t.home.canonicalFile, t.resolve("")!!.canonicalFile)
        assertEquals(t.home.canonicalFile, t.resolve(".")!!.canonicalFile)
    }

    @Test
    fun `a traversal is refused`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        assertNull(t.resolve("../etc/passwd"))
        assertNull(t.resolve("Documents/../../etc/passwd"))
        assertNull(t.resolve("/etc/passwd"))
    }

    @Test
    fun `a guest absolute symlink is rebased on the guest root`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        // What the guest creates: an absolute GUEST path, which does not exist on the host.
        Files.createSymbolicLink(
            File(root.toFile(), "home/omarchy/Notes").toPath(),
            Path.of("/home/omarchy/Documents"),
        )
        val file = t.resolve("Notes/note.txt")
        assertNotNull(file)
        assertEquals("hello", file!!.readText())
    }

    @Test
    fun `a relative symlink resolves against its own directory`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        Files.createSymbolicLink(
            File(root.toFile(), "home/omarchy/Docs").toPath(),
            Path.of("Documents"),
        )
        assertNotNull(t.resolve("Docs/note.txt"))
    }

    @Test
    fun `a symlink that leaves the home is refused`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        File(root.toFile(), "etc").mkdirs()
        File(root.toFile(), "etc/passwd").writeText("root:x:0:0")
        Files.createSymbolicLink(
            File(root.toFile(), "home/omarchy/Escape").toPath(),
            Path.of("/etc/passwd"),
        )
        Files.createSymbolicLink(
            File(root.toFile(), "home/omarchy/Up").toPath(),
            Path.of("../../etc/passwd"),
        )
        assertNull(t.resolve("Escape"))
        assertNull(t.resolve("Up"))
    }

    @Test
    fun `a symlink loop stops at the hop limit`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        Files.createSymbolicLink(
            File(root.toFile(), "home/omarchy/a").toPath(),
            Path.of("/home/omarchy/b"),
        )
        Files.createSymbolicLink(
            File(root.toFile(), "home/omarchy/b").toPath(),
            Path.of("/home/omarchy/a"),
        )
        assertNull(t.resolve("a"))
    }

    @Test
    fun `nothing is served before the guest is extracted`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        File(root.toFile(), ".extraction_complete").delete()
        assertFalse(t.extracted())
        assertNull(t.resolve("Documents"))
        assertTrue(t.children("").isEmpty())
    }

    @Test
    fun `children are directories first and then by name`(
        @TempDir root: Path,
    ) {
        val t = tree(root)
        File(t.home, "zzz").mkdirs()
        File(t.home, "aaa.txt").writeText("a")
        val names = t.children("").map { it.name }
        assertEquals(listOf("Documents", "Pictures", "secret-link-source", "zzz", "aaa.txt"), names)
    }
}
