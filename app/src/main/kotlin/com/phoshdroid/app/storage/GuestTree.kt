package com.phoshdroid.app.storage

import java.io.File
import java.nio.file.Files

/**
 * Maps a document id onto a file inside the guest's home, with the guest's own rules for symlinks.
 *
 * A guest symlink stores an **absolute guest path** (`/home/omarchy/...`, `/usr/share/...`) because
 * it was created by the guest, so resolving it on the host with `File.canonicalPath` would follow a
 * path that exists only inside the guest - or escape into the app's own tree. This class therefore
 * resolves links itself, in guest space:
 *
 *  - every segment is resolved against the guest root, one at a time;
 *  - a link's target is rebased on the guest root (absolute) or on the link's own parent (relative);
 *  - `..` is refused anywhere, in a request or in a link target;
 *  - a path that leaves `/home/omarchy` is refused;
 *  - nothing is served unless the guest is extracted.
 */
class GuestTree(
    private val rootfs: File,
    private val homeGuest: String = DEFAULT_HOME,
    private val maxLinkHops: Int = 16,
) {
    /** The host directory that `homeGuest` maps to. */
    val home: File get() = File(rootfs, homeGuest.trim('/'))

    /** The guest's home for this distro. */
    val homePath: String get() = homeGuest

    /** The extractor's completion marker; without it the guest is not there yet. */
    fun extracted(): Boolean = File(rootfs, ".extraction_complete").exists()

    /**
     * The host file for a document's relative path, or null when it is unservable: not extracted,
     * a traversal, a link that leaves the home, too many link hops, or outside the home.
     */
    fun resolve(relative: String): File? {
        if (!extracted()) return null
        if (relative.startsWith("/")) return null
        val pending = ArrayList<String>()
        for (segment in relative.split('/')) {
            when (segment) {
                "", "." -> {}
                ".." -> return null
                else -> pending.add(segment)
            }
        }
        var guest = homeGuest
        val hops = intArrayOf(0)
        for (segment in pending) {
            val candidate = if (guest == "/") "/$segment" else "$guest/$segment"
            guest = follow(candidate, hops) ?: return null
            if (!insideHome(guest)) return null
        }
        return hostOf(guest)
    }

    /**
     * Follows a chain of symlinks at [candidate] and returns the guest path it ends at. Links are
     * followed in guest space (an absolute target is a guest path, not a host one) and the hop
     * count is shared across the whole request, so a loop terminates.
     */
    private fun follow(candidateIn: String, hops: IntArray): String? {
        var candidate = candidateIn
        while (true) {
            val host = hostOf(candidate) ?: return null
            if (!Files.isSymbolicLink(host.toPath())) return candidate
            if (++hops[0] > maxLinkHops) return null
            val target =
                try {
                    Files.readSymbolicLink(host.toPath()).toString()
                } catch (_: Exception) {
                    return null
                }
            candidate =
                if (target.startsWith("/")) {
                    normalise(target) ?: return null
                } else {
                    normalise("${candidate.substringBeforeLast('/')}/$target") ?: return null
                }
            if (!insideHome(candidate)) return null
        }
    }

    /** The listing of a directory document, directories first and then by name. */
    fun children(relative: String): List<File> {
        val dir = resolve(relative) ?: return emptyList()
        if (!dir.isDirectory) return emptyList()
        val entries = dir.listFiles() ?: return emptyList()
        return entries.sortedWith(
            compareByDescending<File> { it.isDirectory }.thenBy { it.name.lowercase() },
        )
    }

    private fun hostOf(guest: String): File? {
        val normal = normalise(guest) ?: return null
        if (!insideHome(normal)) return null
        return File(rootfs, normal.trim('/'))
    }

    private fun insideHome(guest: String): Boolean =
        guest == homeGuest || guest.startsWith("$homeGuest/")

    /** Lexical normalisation of a guest path; null when it climbs above the guest root. */
    private fun normalise(path: String): String? {
        val out = ArrayList<String>()
        for (segment in path.split('/')) {
            when (segment) {
                "", "." -> {}
                ".." -> {
                    if (out.isEmpty()) return null
                    out.removeAt(out.size - 1)
                }
                else -> out.add(segment)
            }
        }
        return "/" + out.joinToString("/")
    }

    companion object {
        const val DEFAULT_HOME = "/home/omarchy"
    }
}
