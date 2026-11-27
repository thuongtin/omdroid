package com.phoshdroid.app.proot

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test

/** The process tree the host signals when a broker proot will not die (r11 phase 7). */
class ProcTreeTest {
    @Test
    fun `the parent pid is read after the last parenthesis`() {
        assertEquals(1234, ProcTree.parsePpid("5678 (libproot.so) S 1234 5678 5678 0 -1"))
        assertEquals(1234, ProcTree.parsePpid("5678 (a) b) c (d) S 1234 5678 5678 0 -1"))
        assertEquals(7, ProcTree.parsePpid("9 (python3 rootd) R 7 9 9 0 -1"))
    }

    @Test
    fun `a malformed stat line has no parent`() {
        assertNull(ProcTree.parsePpid(""))
        assertNull(ProcTree.parsePpid("5678 libproot.so S 1234"))
        assertNull(ProcTree.parsePpid("5678 (x) S"))
    }

    @Test
    fun `descendants are children and grandchildren of the root only`() {
        // 100 root; 101, 102 children; 103 under 101; 200 and 201 belong to another tree
        val parents = mapOf(100 to 1, 101 to 100, 102 to 100, 103 to 101, 200 to 1, 201 to 200)
        assertEquals(listOf(101, 102, 103), ProcTree.descendantsOf(100, parents).sorted())
        assertEquals(emptyList<Int>(), ProcTree.descendantsOf(103, parents))
        assertEquals(listOf(201), ProcTree.descendantsOf(200, parents))
    }

    @Test
    fun `a pid cycle in the table cannot loop forever`() {
        val parents = mapOf(10 to 11, 11 to 10, 12 to 10)
        assertEquals(listOf(11, 12), ProcTree.descendantsOf(10, parents).sorted())
    }

    @Test
    fun `the process stoppable signals the descendants before the process itself`() {
        val order = mutableListOf<String>()
        val real = ProcessBuilder("sleep", "30").start()
        try {
            val pid = ProcTree.pidOf(real)
            assertEquals(true, pid > 0)
            val s = JavaProcessStoppable(real) { p, sig -> order += "tree:$p:$sig" }
            s.destroy()
            assertEquals(true, s.waitFor(2000))
            assertEquals(listOf("tree:$pid:15"), order)
        } finally {
            real.destroyForcibly()
        }
    }
}
