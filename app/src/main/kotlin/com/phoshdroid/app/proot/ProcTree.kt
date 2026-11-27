package com.phoshdroid.app.proot

import java.io.File

/**
 * The processes below a pid, read from /proc (same uid, so readable without root).
 *
 * Why: the fake-root broker proot did not end when the host sent it SIGTERM and then SIGKILL on the
 * device (r11 phase 7: three guest-exit paths, `root-broker still alive after SIGKILL`, the process
 * still listed with its python child), and it did end as soon as the python child was killed from
 * inside the guest (phase 7 C, `TERMINATED` 35 ms after the child exited). So the host signals the
 * descendants as well. The cause of the ignored signal is not found; this is a workaround that was
 * measured, not an explanation.
 */
object ProcTree {
    /** Parent pid out of a `/proc/<pid>/stat` line; the command name may hold spaces and parentheses. */
    fun parsePpid(stat: String): Int? {
        val close = stat.lastIndexOf(')')
        if (close < 0) return null
        val rest = stat.substring(close + 1).trim().split(' ')
        return rest.getOrNull(1)?.toIntOrNull()
    }

    /** Every pid below [root] (children, grandchildren, ...), parents before children. */
    fun descendantsOf(
        root: Int,
        parentOf: Map<Int, Int>,
    ): List<Int> {
        val byParent = parentOf.entries.groupBy({ it.value }, { it.key })
        val out = mutableListOf<Int>()
        val queue = ArrayDeque(byParent[root].orEmpty())
        while (queue.isNotEmpty()) {
            val pid = queue.removeFirst()
            if (pid == root || pid in out) continue
            out += pid
            queue.addAll(byParent[pid].orEmpty())
        }
        return out
    }

    fun readParents(proc: File = File("/proc")): Map<Int, Int> {
        val parents = HashMap<Int, Int>()
        proc.listFiles()?.forEach { dir ->
            val pid = dir.name.toIntOrNull() ?: return@forEach
            val ppid =
                try {
                    parsePpid(File(dir, "stat").readText())
                } catch (_: Exception) {
                    null
                }
            if (ppid != null) parents[pid] = ppid
        }
        return parents
    }

    fun descendants(root: Int): List<Int> = descendantsOf(root, readParents())

    /** One line of facts about a process that will not die, for the log. */
    fun status(pid: Int): String =
        try {
            val keys = setOf("State", "PPid", "TracerPid", "Threads", "SigIgn", "SigBlk")
            File("/proc/$pid/status")
                .readLines()
                .mapNotNull { line ->
                    val k = line.substringBefore(':')
                    if (k in keys) "$k=${line.substringAfter(':').trim()}" else null
                }.joinToString(" ")
        } catch (e: Exception) {
            "unreadable (${e.message})"
        }

    /** The pid inside `Process[pid=123, ...]`, or -1. */
    fun pidOf(process: Process): Int =
        Regex("pid=(\\d+)").find(process.toString())?.groupValues?.get(1)?.toIntOrNull() ?: -1
}
