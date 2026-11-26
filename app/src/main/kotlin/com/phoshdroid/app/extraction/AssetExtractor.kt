package com.phoshdroid.app.extraction

import com.github.luben.zstd.ZstdInputStream
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream
import java.io.BufferedInputStream
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.util.zip.GZIPInputStream

class AssetExtractor {

    /** Hard-link members that could not be materialised from their target. */
    var skippedLinks: Int = 0
        private set

    fun extract(
        input: InputStream,
        totalBytes: Long,
        targetDir: File,
        onProgress: (percent: Int) -> Unit = {}
    ): Boolean {
        skippedLinks = 0
        val marker = File(targetDir, ".extraction_complete")
        if (marker.exists()) return false

        targetDir.mkdirs()
        var bytesRead = 0L
        var lastPercent = -1

        CountingInputStream(input) { count ->
            bytesRead = count
            val percent = if (totalBytes > 0) ((count * 100) / totalBytes).toInt().coerceAtMost(100) else 0
            if (percent != lastPercent) {
                lastPercent = percent
                onProgress(percent)
            }
        }.let { counting ->
            TarArchiveInputStream(decompress(BufferedInputStream(counting))).use { tar ->
                var entry = tar.nextEntry
                while (entry != null) {
                    val outFile = File(targetDir, entry.name)
                    if (entry.isDirectory) {
                        outFile.mkdirs()
                    } else if (entry.isSymbolicLink) {
                        outFile.parentFile?.mkdirs()
                        outFile.delete()
                        Runtime.getRuntime().exec(
                            arrayOf("ln", "-sf", entry.linkName, outFile.absolutePath)
                        ).waitFor()
                    } else if (entry.isLink) {
                        // Hard-link member into the archive (terminfo and zoneinfo
                        // aliases); the entry carries no data, so the member has to
                        // be materialised from its target. Android denies apps hard
                        // links inside app data, and the old `ln -f` failed without
                        // throwing, which silently left these members missing on
                        // device; copy the target instead (all copies together are
                        // only a few megabytes).
                        outFile.parentFile?.mkdirs()
                        outFile.delete()
                        val target = File(targetDir, entry.linkName)
                        try {
                            if (target.isFile) {
                                target.copyTo(outFile, overwrite = true)
                                if (target.canExecute()) {
                                    outFile.setExecutable(true)
                                }
                            } else {
                                skippedLinks++
                            }
                        } catch (_: Exception) {
                            skippedLinks++
                        }
                    } else {
                        outFile.parentFile?.mkdirs()
                        java.io.BufferedOutputStream(outFile.outputStream()).use { out ->
                            tar.copyTo(out)
                        }
                        if (entry.mode and 0b001_001_001 != 0) {
                            outFile.setExecutable(true)
                        }
                    }
                    entry = tar.nextEntry
                }
            }
        }

        onProgress(100)
        marker.createNewFile()
        return true
    }

    /**
     * Picks the decompressor from the stream's own magic bytes: gzip for
     * `bootstrap.bin` (and every `rootfs.bin` up to 0.0.17) and zstd for the
     * 0.0.18 guest image, so an updated APK still extracts an old asset and the
     * bootstrap keeps its format. Unknown bytes fail loudly instead of letting
     * the tar reader report a truncated archive.
     */
    private fun decompress(input: BufferedInputStream): InputStream {
        input.mark(MAGIC_BYTES)
        val magic = ByteArray(MAGIC_BYTES)
        var read = 0
        while (read < magic.size) {
            val n = input.read(magic, read, magic.size - read)
            if (n < 0) break
            read += n
        }
        input.reset()
        return when {
            read >= 2 && magic[0] == GZIP_MAGIC_0 && magic[1] == GZIP_MAGIC_1 ->
                GZIPInputStream(input)
            read >= 4 && magic.copyOf(4).contentEquals(ZSTD_MAGIC) ->
                ZstdInputStream(input)
            else ->
                throw IOException(
                    "unknown image compression: " +
                        magic.take(read).joinToString(" ") { "%02x".format(it) }
                )
        }
    }

    private companion object {
        const val MAGIC_BYTES = 4
        val GZIP_MAGIC_0: Byte = 0x1f
        val GZIP_MAGIC_1: Byte = 0x8b.toByte()
        val ZSTD_MAGIC = byteArrayOf(0x28, 0xb5.toByte(), 0x2f, 0xfd.toByte())
    }
}

private class CountingInputStream(
    private val wrapped: InputStream,
    private val onBytesRead: (Long) -> Unit
) : InputStream() {

    private var totalRead = 0L

    override fun read(): Int {
        val b = wrapped.read()
        if (b >= 0) {
            totalRead++
            onBytesRead(totalRead)
        }
        return b
    }

    override fun read(b: ByteArray, off: Int, len: Int): Int {
        val n = wrapped.read(b, off, len)
        if (n > 0) {
            totalRead += n
            onBytesRead(totalRead)
        }
        return n
    }

    override fun close() = wrapped.close()
}
